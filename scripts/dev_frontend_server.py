"""Development-only static server with SPA fallback.

The production edge (nginx/Caddy) rewrites unknown UI routes to the SPA shell.
`python -m http.server` does not, so deep links like /projects/12 or /operations
404 locally and cannot be tested. This server serves frontend/ and falls back to
the SPA shell for unknown *UI* routes, while leaving real files and /api alone.

Usage:  python scripts/dev_frontend_server.py [--port 3000] [--root frontend]
Never used in production.
"""
from __future__ import annotations

import argparse
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

# Requests starting with these are never rewritten (real API / assets).
_NO_FALLBACK = ("/api/", "/assets/", "/data/", "/static/")
_SHELL = "index.html"


class SPAFallbackHandler(SimpleHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 (stdlib naming)
        path = self.path.split("?", 1)[0].split("#", 1)[0]
        fs_path = self.translate_path(path)

        # Serve real files and real directories (with their own index.html) as-is.
        if os.path.isfile(fs_path):
            return super().do_GET()
        if os.path.isdir(fs_path) and os.path.isfile(os.path.join(fs_path, _SHELL)):
            return super().do_GET()
        if path.startswith(_NO_FALLBACK) or "." in os.path.basename(path):
            return super().do_GET()  # let it 404 honestly (missing asset)

        # Unknown UI route (/projects/12, /video/7, /operations, /create/video…)
        # -> serve the SPA shell so the client router can handle it. The root
        # index.html is the marketing landing, so app routes get the app shell
        # (dashboard/index.html), matching what the production edge serves.
        self.path = "/dashboard/" + _SHELL if path != "/" else "/" + _SHELL
        return super().do_GET()

    def log_message(self, fmt, *args):  # quieter dev output
        pass


def main() -> None:
    ap = argparse.ArgumentParser(description="Dev static server with SPA fallback")
    ap.add_argument("--port", type=int, default=3000)
    ap.add_argument("--root", default="frontend")
    args = ap.parse_args()
    root = os.path.abspath(args.root)
    handler = partial(SPAFallbackHandler, directory=root)
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(f"dev frontend (SPA fallback) on http://localhost:{args.port}  root={root}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
