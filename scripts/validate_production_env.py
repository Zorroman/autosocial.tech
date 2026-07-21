#!/usr/bin/env python3
"""Production environment validator — local, read-only, fail-closed.

Checks the current process environment (or a given --env-file) for a safe
production configuration. Never prints secret values; only PRESENT / MISSING /
INVALID / WEAK and, at most, the last 4 characters of a value when needed.

Exit code 0 only when the configuration is safe for production. Any critical
problem -> exit 1. It performs NO network calls and touches NO database.

Usage:
    ENV=production ... python scripts/validate_production_env.py
    python scripts/validate_production_env.py --env-file /path/to/.env
    python scripts/validate_production_env.py --require production
"""
import argparse
import os
import re
import shutil
import sys

MIN_SECRET_LEN = 32          # Flask secret / token key minimum length
LOCAL_HOST_RE = re.compile(r"://(localhost|127\.0\.0\.1|0\.0\.0\.0)\b", re.I)


class Result:
    def __init__(self):
        self.critical: list[str] = []
        self.warnings: list[str] = []
        self.info: list[str] = []

    def crit(self, name, msg):
        self.critical.append(f"[CRITICAL] {name}: {msg}")

    def warn(self, name, msg):
        self.warnings.append(f"[WARN] {name}: {msg}")

    def ok(self, name, msg="PRESENT"):
        self.info.append(f"[OK] {name}: {msg}")


def _load_env_file(path: str) -> dict:
    env = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def _get(env, key, default=""):
    return (env.get(key, default) or "").strip()


def _bool(env, key):
    return _get(env, key).lower() in {"1", "true", "yes"}


def validate(env: dict, require_env: str | None = None) -> Result:
    r = Result()
    ENV = _get(env, "ENV") or "development"
    is_prod = ENV.lower() in {"production", "prod"}
    if require_env and ENV.lower() != require_env.lower():
        r.crit("ENV", f"expected '{require_env}', got '{ENV}'")
    r.ok("ENV", ENV)

    # --- private admin (fail closed) ---
    if not _bool(env, "PRIVATE_ADMIN_MODE"):
        r.crit("PRIVATE_ADMIN_MODE", "must be true for this single-admin product")
    allowlist = [e for e in _get(env, "ADMIN_ALLOWLIST_EMAILS").split(",") if e.strip()]
    if not allowlist:
        r.crit("ADMIN_ALLOWLIST_EMAILS", "empty -> fail closed, no admin can log in")
    else:
        r.ok("ADMIN_ALLOWLIST_EMAILS", f"{len(allowlist)} entr{'y' if len(allowlist)==1 else 'ies'}")

    # --- cookies / transport ---
    if is_prod and not _bool(env, "COOKIE_SECURE"):
        r.crit("COOKIE_SECURE", "must be true in production (HTTPS-only cookies)")
    else:
        r.ok("COOKIE_SECURE", str(_bool(env, "COOKIE_SECURE")))

    # --- encryption / secret strength ---
    tek = _get(env, "TOKEN_ENCRYPTION_KEY")
    if not tek:
        r.crit("TOKEN_ENCRYPTION_KEY", "MISSING (required to store OAuth tokens)")
    elif len(tek) < MIN_SECRET_LEN:
        r.crit("TOKEN_ENCRYPTION_KEY", f"WEAK (len {len(tek)} < {MIN_SECRET_LEN})")
    else:
        r.ok("TOKEN_ENCRYPTION_KEY", f"strong (len {len(tek)})")

    # Flask session secret: accept SECRET_KEY or FLASK_SECRET_KEY.
    flask_secret = _get(env, "SECRET_KEY") or _get(env, "FLASK_SECRET_KEY")
    if is_prod:
        if not flask_secret:
            r.crit("SECRET_KEY", "MISSING (Flask session signing secret)")
        elif len(flask_secret) < MIN_SECRET_LEN or flask_secret in {"dev", "change_me", "secret"}:
            r.crit("SECRET_KEY", f"WEAK (len {len(flask_secret)})")
        else:
            r.ok("SECRET_KEY", f"strong (len {len(flask_secret)})")

    # --- data stores ---
    db = _get(env, "DATABASE_URL")
    if not db:
        r.crit("DATABASE_URL", "MISSING")
    else:
        if is_prod and db.startswith("sqlite"):
            r.warn("DATABASE_URL", "sqlite in production is discouraged (use PostgreSQL)")
        r.ok("DATABASE_URL", "PRESENT")

    sync_jobs = _bool(env, "SYNC_JOBS")
    redis = _get(env, "REDIS_URL")
    if not redis and not sync_jobs:
        r.crit("REDIS_URL", "MISSING and SYNC_JOBS is false -> render/upload queue cannot run")
    elif not redis and sync_jobs:
        r.warn("REDIS_URL", "MISSING but SYNC_JOBS=true (in-process jobs, lost on restart)")
    else:
        r.ok("REDIS_URL", "PRESENT")

    # --- OpenAI (must be present as a variable; empty is allowed) ---
    if "OPENAI_API_KEY" not in env:
        r.crit("OPENAI_API_KEY", "variable absent -> app import fails (legacy pipeline)")
    else:
        r.ok("OPENAI_API_KEY", "declared" + ("" if _get(env, "OPENAI_API_KEY") else " (empty; AI features degraded)"))

    # --- provider / mock consistency ---
    if is_prod and _bool(env, "USE_MOCK_PROVIDERS"):
        r.crit("USE_MOCK_PROVIDERS", "true in production (mock media/meta providers)")
    if is_prod and _get(env, "VISUAL_AI_PROVIDER").lower() == "mock" and _bool(env, "VISUAL_VALIDATION_ENABLED"):
        r.crit("VISUAL_AI_PROVIDER", "mock while VISUAL_VALIDATION_ENABLED=true in production")

    # --- publishing safety ---
    # There is no global auto-publish switch; it is per-channel and defaults OFF.
    # Flag any accidental global override some future env var might introduce.
    if _bool(env, "AUTOMATIC_PUBLISHING_GLOBAL") or _bool(env, "GLOBAL_AUTO_PUBLISH"):
        r.crit("AUTOMATIC_PUBLISHING", "global auto-publish override enabled without explicit opt-in policy")
    else:
        r.ok("AUTOMATIC_PUBLISHING", "per-channel, default OFF")

    # --- YouTube consistency (disabled is a valid production state) ---
    yt = _youtube_readiness(env, is_prod)
    for level, name, msg in yt:
        getattr(r, level)(name, msg)

    # --- Stripe consistency (disabled is a valid production state) ---
    st = _stripe_readiness(env, is_prod)
    for level, name, msg in st:
        getattr(r, level)(name, msg)

    # --- FFmpeg / ffprobe ---
    for binkey, default in (("FFMPEG_BIN", "ffmpeg"), ("FFPROBE_BIN", "ffprobe")):
        binv = _get(env, binkey) or default
        found = shutil.which(binv) or (os.path.isfile(binv) and os.access(binv, os.X_OK))
        (r.ok if found else r.crit)(binkey, "found" if found else f"NOT FOUND ('{binv}')")

    # --- writable dirs ---
    base = _get(env, "BASE_DIR") or os.getcwd()
    for sub in ("output/videos", "output/audio", "output/subtitles", "output/manifests", "cache/footage"):
        d = os.path.join(base, sub)
        parent = d
        while parent and not os.path.isdir(parent):
            parent = os.path.dirname(parent)
        if parent and not os.access(parent, os.W_OK):
            r.crit("WRITABLE_DIR", f"{d} not writable")
    r.ok("WRITABLE_DIRS", f"under {base}")

    return r


def _youtube_readiness(env, is_prod) -> list[tuple]:
    """YouTube disabled is valid. If any credential is set, all must be set and
    consistent (HTTPS, non-localhost redirect, token encryption present)."""
    cid = _get(env, "GOOGLE_CLIENT_ID")
    csec = _get(env, "GOOGLE_CLIENT_SECRET")
    redirect = _get(env, "YOUTUBE_REDIRECT_URI")
    any_set = any((cid, csec, redirect))
    out = []
    if not any_set:
        out.append(("ok", "YOUTUBE", "disabled (valid production state)"))
        return out
    if not (cid and csec):
        out.append(("crit", "YOUTUBE", "partial credentials (need client id AND secret)"))
    if not redirect:
        out.append(("crit", "YOUTUBE", "YOUTUBE_REDIRECT_URI missing while enabled"))
    else:
        if is_prod and LOCAL_HOST_RE.search(redirect):
            out.append(("crit", "YOUTUBE_REDIRECT_URI", "localhost redirect in production"))
        if is_prod and not redirect.lower().startswith("https://"):
            out.append(("crit", "YOUTUBE_REDIRECT_URI", "callback must be HTTPS in production"))
    if not _get(env, "TOKEN_ENCRYPTION_KEY"):
        out.append(("crit", "YOUTUBE", "token encryption key required when YouTube is enabled"))
    if not [o for o in out if o[0] == "crit"]:
        out.append(("ok", "YOUTUBE", "enabled, consistent"))
    return out


def _stripe_readiness(env, is_prod) -> list[tuple]:
    """Stripe disabled is valid. If enabled, secret + webhook + prices + URLs
    must all be present and consistent."""
    enabled_flag = _bool(env, "STRIPE_ENABLED")
    sk = _get(env, "STRIPE_SECRET_KEY")
    wh = _get(env, "STRIPE_WEBHOOK_SECRET")
    any_set = enabled_flag or any((sk, wh))
    out = []
    if not any_set:
        out.append(("ok", "STRIPE", "disabled (valid production state)"))
        return out
    if not sk:
        out.append(("crit", "STRIPE", "enabled but STRIPE_SECRET_KEY missing"))
    if not wh:
        out.append(("crit", "STRIPE", "enabled but STRIPE_WEBHOOK_SECRET missing"))
    if is_prod and sk.startswith("sk_test_"):
        out.append(("warn", "STRIPE_SECRET_KEY", "TEST key in production"))
    for u in ("STRIPE_SUCCESS_URL", "STRIPE_CANCEL_URL"):
        val = _get(env, u)
        if val and is_prod and not val.lower().startswith("https://"):
            out.append(("crit", u, "must be HTTPS in production"))
    if not [o for o in out if o[0] == "crit"]:
        out.append(("ok", "STRIPE", "enabled, consistent"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate production environment (read-only, no network).")
    ap.add_argument("--env-file", help="Read variables from this file instead of the process env")
    ap.add_argument("--require", help="Require ENV to equal this value (e.g. production)")
    ap.add_argument("--quiet", action="store_true", help="Only print the verdict line")
    args = ap.parse_args()

    env = _load_env_file(args.env_file) if args.env_file else dict(os.environ)
    r = validate(env, require_env=args.require)

    if not args.quiet:
        for line in r.info:
            print(line)
        for line in r.warnings:
            print(line)
        for line in r.critical:
            print(line)
        print("-" * 50)
    ok = not r.critical
    print(f"PRODUCTION ENV: {'VALID' if ok else 'INVALID'} "
          f"({len(r.critical)} critical, {len(r.warnings)} warnings)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
