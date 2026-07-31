"""Production deployment hardening tests.

Covers: publishing fail-safe default, production env validator, deployed
frontend verifier, deployment lock, backup/migration safety, and dry-run
rollback behavior. All local, no network, no production access.
"""
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
PY = sys.executable


# ============================================================ publishing default

def test_channel_model_default_publishing_off():
    from app_models import Channel
    col = Channel.__table__.c.automatic_publishing_enabled
    assert col.default.arg is False, "new channels must default to auto-publish OFF"
    assert Channel.__table__.c.automatic_generation_enabled.default.arg is False


def test_migration_ddl_publishing_off():
    src = (ROOT / "migrations.py").read_text(encoding="utf-8")
    assert '"automatic_publishing_enabled": "BOOLEAN DEFAULT 0"' in src
    assert '"automatic_publishing_enabled": "BOOLEAN DEFAULT 1"' not in src


@pytest.fixture()
def client(tmp_path):
    # fresh app on an isolated DB
    for m in ("app", "database", "app_models", "app_settings", "channels_api",
              "content_api", "content_director", "content_director_api",
              "publications_api", "video_projects_api", "migrations"):
        sys.modules.pop(m, None)
    from tests.test_private_admin import _fresh_app, _seed_admin, _token_for
    app_module = _fresh_app(tmp_path)
    admin_id = _seed_admin()
    with app_module.app.test_client() as c:
        c.token = _token_for(admin_id)
        c.admin_id = admin_id
        yield c


def _h(c):
    return {"Authorization": f"Bearer {c.token}"}


def test_new_channel_publishing_disabled(client):
    ch = client.post("/api/channels", json={"name": "Fresh"}, headers=_h(client)).get_json()["channel"]
    assert ch["automatic_publishing_enabled"] is False        # (1) new channel off
    assert ch["automatic_generation_enabled"] is False


def test_missing_field_is_failsafe_disabled(client):
    # (2)+(3) The serializer maps a missing/None flag to False, never True.
    # The column is NOT NULL so NULL cannot arise via the ORM; the serializer's
    # bool() is the belt-and-suspenders fail-safe against any None value.
    import types
    import channels_api
    stub = types.SimpleNamespace(
        id=1, name="x", slug="x", niche=None, description=None, language="ru",
        target_audience=None, content_style=None, narration_style=None,
        default_voice=None, visual_style=None, categories_json=None,
        allowed_topics=None, prohibited_topics=None,
        default_video_duration_seconds=45, default_video_format="shorts",
        publication_frequency=None, timezone="UTC", status="testing",
        niche_id=None, target_country=None, tone_of_voice=None,
        daily_video_limit=0, default_visibility="private",
        automatic_generation_enabled=None, automatic_publishing_enabled=None,
        last_generated_at=None, youtube_channel_id=None, connected_account_id=None,
        generation_settings_json=None, video_template_json=None,
        subtitle_template_json=None, music_settings_json=None,
        created_at=None, updated_at=None,
    )
    d = channels_api._channel_dict(stub)
    assert d["automatic_publishing_enabled"] is False
    assert d["automatic_generation_enabled"] is False


def test_explicit_enable_and_disable(client):
    ch = client.post("/api/channels", json={"name": "Toggle"}, headers=_h(client)).get_json()["channel"]["id"]
    # (5) explicit disable is idempotent-safe
    client.patch(f"/api/channels/{ch}", json={"automatic_publishing_enabled": False}, headers=_h(client))
    assert client.get(f"/api/channels/{ch}", headers=_h(client)).get_json()["channel"]["automatic_publishing_enabled"] is False
    # (4) explicit enable works (needs no YouTube for the flag itself)
    client.patch(f"/api/channels/{ch}", json={"automatic_publishing_enabled": True}, headers=_h(client))
    assert client.get(f"/api/channels/{ch}", headers=_h(client)).get_json()["channel"]["automatic_publishing_enabled"] is True


def _seed_ch_with_niche(client):
    from content_api import seed_esotericism
    from database import SessionLocal
    db = SessionLocal(); nid = seed_esotericism(db).id; db.close()
    ch = client.post("/api/channels", json={"name": "Dir"}, headers=_h(client)).get_json()["channel"]["id"]
    client.patch(f"/api/channels/{ch}", json={"niche_id": nid, "daily_video_limit": 5}, headers=_h(client))
    return ch


def test_director_approve_does_not_enable_publishing(client, monkeypatch):
    # (6) Director approve creates a project but never flips the publish flag
    monkeypatch.setenv("DIRECTOR_USE_AI", "false")
    ch = _seed_ch_with_niche(client)
    s = client.post("/api/content-director/generate", json={"channel_id": ch}, headers=_h(client)).get_json()["strategy"]
    client.post("/api/content-director/approve", json={"strategy_id": s["id"]}, headers=_h(client))
    assert client.get(f"/api/channels/{ch}", headers=_h(client)).get_json()["channel"]["automatic_publishing_enabled"] is False


def test_youtube_link_does_not_enable_publishing(client, monkeypatch):
    # (7) connecting a YouTube channel must not enable auto publishing
    import publications_api as pa
    ch = client.post("/api/channels", json={"name": "YT"}, headers=_h(client)).get_json()["channel"]["id"]
    from database import SessionLocal
    from app_models import SocialAccount
    db = SessionLocal()
    acc = SocialAccount(user_id=client.admin_id, provider="youtube", status="connected_ready",
                        token_encrypted="x", token_expires_at=__import__("datetime").datetime.utcnow()
                        + __import__("datetime").timedelta(hours=1))
    db.add(acc); db.commit(); db.refresh(acc); db.close()
    monkeypatch.setattr(pa, "_valid_account_token", lambda db, a: "tok")
    monkeypatch.setattr(pa, "_yt_list_my_channels", lambda tok: ([{"id": "UCx", "title": "My"}], None))
    r = client.post(f"/api/channels/{ch}/youtube/link", json={"youtube_channel_id": "UCx"}, headers=_h(client))
    assert r.status_code == 200
    assert client.get(f"/api/channels/{ch}", headers=_h(client)).get_json()["channel"]["automatic_publishing_enabled"] is False


def test_migration_preserves_existing_rows(tmp_path):
    # (8) a DB that already has the column with value 1 keeps it after migration
    import sqlite3
    dbp = tmp_path / "existing.db"
    con = sqlite3.connect(dbp)
    con.executescript("""
        CREATE TABLE channels (id INTEGER PRIMARY KEY, owner_user_id INTEGER, name TEXT,
            slug TEXT, automatic_publishing_enabled BOOLEAN DEFAULT 1);
        INSERT INTO channels (id, name, slug, automatic_publishing_enabled) VALUES (1,'old','old',1);
    """)
    con.commit(); con.close()
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{dbp}"}
    subprocess.run([PY, "migrations.py"], cwd=ROOT, env=env, check=True, capture_output=True)
    con = sqlite3.connect(dbp)
    val = con.execute("SELECT automatic_publishing_enabled FROM channels WHERE id=1").fetchone()[0]
    con.close()
    assert val == 1, "existing row value must be preserved by additive migration"


# ============================================================ production validator

def _run_validator(env):
    full = {"PATH": os.environ["PATH"]}
    full.update(env)
    return subprocess.run([PY, str(SCRIPTS / "validate_production_env.py"), "--quiet"],
                          env=full, capture_output=True, text=True)


def _valid_prod_env():
    ff = shutil.which("ffmpeg") or "ffmpeg"
    fp = shutil.which("ffprobe") or "ffprobe"
    return {
        "ENV": "production", "PRIVATE_ADMIN_MODE": "true", "COOKIE_SECURE": "true",
        "ADMIN_ALLOWLIST_EMAILS": "admin@x.io", "TOKEN_ENCRYPTION_KEY": "k" * 44,
        "SECRET_KEY": "s" * 44, "DATABASE_URL": "postgresql://h/db",
        "REDIS_URL": "redis://h:6379/0", "OPENAI_API_KEY": "", "FFMPEG_BIN": ff,
        "FFPROBE_BIN": fp, "BASE_DIR": "/tmp",
    }


def test_validator_valid_minimal():
    assert _run_validator(_valid_prod_env()).returncode == 0


@pytest.mark.parametrize("mutate,expect_fail", [
    ({"ADMIN_ALLOWLIST_EMAILS": ""}, True),                 # missing allowlist
    ({"TOKEN_ENCRYPTION_KEY": "short"}, True),              # weak encryption key
    ({"COOKIE_SECURE": "false"}, True),                     # insecure cookies
    ({"DATABASE_URL": ""}, True),                           # missing database
    ({"REDIS_URL": "", "SYNC_JOBS": "false"}, True),        # missing redis, no sync
    ({"SECRET_KEY": "dev"}, True),                          # weak flask secret
    ({"GOOGLE_CLIENT_ID": "abc"}, True),                    # partial youtube
    ({"GOOGLE_CLIENT_ID": "a", "GOOGLE_CLIENT_SECRET": "b",
      "YOUTUBE_REDIRECT_URI": "http://localhost/cb"}, True),  # localhost redirect
    ({"STRIPE_SECRET_KEY": "sk_test_x"}, True),             # partial stripe (no webhook)
    ({"USE_MOCK_PROVIDERS": "true"}, True),                 # mock in prod
    ({"GLOBAL_AUTO_PUBLISH": "true"}, True),                # unsafe global publish
])
def test_validator_fail_cases(mutate, expect_fail):
    env = _valid_prod_env(); env.update(mutate)
    rc = _run_validator(env).returncode
    assert (rc != 0) is expect_fail, f"{mutate} -> rc={rc}"


def test_validator_stripe_disabled_ok():
    env = _valid_prod_env()  # no stripe vars => disabled => valid
    assert _run_validator(env).returncode == 0


def test_validator_missing_openai_var_fails():
    env = _valid_prod_env(); env.pop("OPENAI_API_KEY")
    # explicitly ensure the var is absent (not just empty)
    r = subprocess.run([PY, str(SCRIPTS / "validate_production_env.py"), "--quiet"],
                       env={"PATH": os.environ["PATH"], **env}, capture_output=True, text=True)
    assert r.returncode != 0


# ============================================================ frontend verifier

def _sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _run_verifier(sha, path):
    return subprocess.run(["bash", str(SCRIPTS / "verify_deployed_frontend.sh"), sha, str(path)],
                          capture_output=True, text=True)


def test_verifier_valid_file():
    p = ROOT / "frontend/app.js"
    assert _run_verifier(_sha(p), p).returncode == 0


def test_verifier_wrong_sha(tmp_path):
    p = ROOT / "frontend/app.js"
    assert _run_verifier("0" * 64, p).returncode != 0


def test_verifier_truncated(tmp_path):
    p = tmp_path / "app.js"
    p.write_text("function render(){}\n")  # tiny -> below min size
    assert _run_verifier(_sha(p), p).returncode != 0


def test_verifier_invalid_utf8(tmp_path):
    p = tmp_path / "app.js"
    body = b"function render(){}\n" + b"x" * 500000 + b"\xff\xfe bad bytes"
    p.write_bytes(body)
    assert _run_verifier(_sha(p), p).returncode != 0


def test_verifier_excessive_qmarks(tmp_path):
    p = tmp_path / "app.js"
    p.write_text("function render(){}\n" + ("????" * 10) + "x" * 500000 + ";")
    assert _run_verifier(_sha(p), p).returncode != 0


def test_verifier_conflict_marker(tmp_path):
    p = tmp_path / "app.js"
    p.write_text("function render(){}\n" + "<" * 7 + " HEAD\n" + "x" * 500000 + ";")
    assert _run_verifier(_sha(p), p).returncode != 0


def test_verifier_syntax_error(tmp_path):
    p = tmp_path / "app.js"
    # valid markers + size but broken JS
    p.write_text("function render( pageContentDirector pageFactoryDashboard nav( { ( "
                 + "x" * 500000 + " ;;;)))")
    r = _run_verifier(_sha(p), p)
    if shutil.which("node"):
        assert r.returncode != 0


def test_verifier_missing_marker(tmp_path):
    p = tmp_path / "app.js"
    p.write_text("var x = 1;\n" + "y".join(["z"] * 500000) + ";")  # big, valid JS, no markers
    assert _run_verifier(_sha(p), p).returncode != 0


# ============================================================ deploy dry-run

@pytest.fixture()
def deploy_env(tmp_path):
    app = tmp_path / "app"; (app / "frontend").mkdir(parents=True); (app / "logs").mkdir()
    shutil.copy(ROOT / "frontend/app.js", app / "frontend/app.js")
    import sqlite3
    con = sqlite3.connect(app / "autosocial.db")
    con.execute("CREATE TABLE t(x)"); con.execute("INSERT INTO t VALUES(1)"); con.commit(); con.close()
    sha = _sha(ROOT / "frontend/app.js")
    base = {**os.environ, "DEPLOY_DRY_RUN": "1", "APP_DIR": str(app), "RELEASE_SOURCE": str(ROOT),
            "BACKUP_DIR": str(tmp_path / "backups"), "LOCK_FILE": str(tmp_path / "deploy.lock"),
            "TARGET_COMMIT": "HEADSHA", "FRONTEND_EXPECTED_SHA": sha}
    return app, sha, base


def _run_deploy(env):
    return subprocess.run(["bash", str(SCRIPTS / "deploy_production.sh")],
                          env=env, capture_output=True, text=True)


def test_deploy_dry_run_success(deploy_env):
    app, sha, env = deploy_env
    r = _run_deploy(env)
    assert r.returncode == 0, r.stderr + r.stdout
    assert "DEPLOY SUCCEEDED" in r.stdout
    backups = list((Path(env["BACKUP_DIR"])).glob("db_*.db"))
    assert backups and backups[0].stat().st_size > 0          # backup created + non-empty
    assert not Path(env["LOCK_FILE"] + ".d").exists()          # lock released


def test_deploy_sha_mismatch_blocks_activation(deploy_env):
    app, sha, env = deploy_env
    env = {**env, "FRONTEND_EXPECTED_SHA": "0" * 64}
    # keep a marker of the current (correct) app.js to prove it is untouched
    before = _sha(app / "frontend/app.js")
    r = _run_deploy(env)
    assert r.returncode != 0
    assert "NOT activating" in (r.stdout + r.stderr) or "integrity" in (r.stdout + r.stderr)
    assert _sha(app / "frontend/app.js") == before             # previous frontend preserved
    assert not Path(env["LOCK_FILE"] + ".d").exists()          # lock released after failure


def test_deploy_migration_failure_blocks_activation(deploy_env, tmp_path):
    app, sha, env = deploy_env
    # point RELEASE_SOURCE at a copy whose migrations.py fails
    rel = tmp_path / "badrelease"
    shutil.copytree(ROOT, rel, ignore=shutil.ignore_patterns(".venv", ".git", "__pycache__",
                                                             "output", "cache", "data", "*.db"))
    (rel / "migrations.py").write_text("import sys; sys.exit(2)\n")
    (rel / "frontend").mkdir(exist_ok=True)
    shutil.copy(ROOT / "frontend/app.js", rel / "frontend/app.js")
    before = _sha(app / "frontend/app.js")
    env = {**env, "RELEASE_SOURCE": str(rel)}
    r = _run_deploy(env)
    assert r.returncode != 0
    assert "migrations failed" in (r.stdout + r.stderr).lower()
    assert _sha(app / "frontend/app.js") == before             # not activated
    assert list(Path(env["BACKUP_DIR"]).glob("db_*.db"))        # DB backup intact
    assert not Path(env["LOCK_FILE"] + ".d").exists()


def test_deploy_empty_backup_rejected(deploy_env, tmp_path):
    app, sha, env = deploy_env
    # A zero-byte sqlite source still yields a valid (non-empty) backup, so to
    # exercise the empty-backup guard deterministically we drive the pg_dump
    # branch with a stub pg_dump that succeeds but emits nothing.
    (app / "autosocial.db").unlink()                 # force the DATABASE_URL branch
    stub_bin = tmp_path / "bin"; stub_bin.mkdir()
    (stub_bin / "pg_dump").write_text("#!/usr/bin/env bash\nexit 0\n")   # no output
    (stub_bin / "pg_dump").chmod(0o755)
    env = {**env, "DATABASE_URL": "postgresql://x/y",
           "PATH": str(stub_bin) + os.pathsep + env["PATH"]}
    r = _run_deploy(env)
    assert r.returncode != 0
    assert "backup is empty" in (r.stdout + r.stderr).lower()


def test_deploy_lock_prevents_concurrent(deploy_env):
    app, sha, env = deploy_env
    # pre-create the lock dir to simulate a held lock
    lock_dir = Path(env["LOCK_FILE"] + ".d")
    lock_dir.mkdir(parents=True)
    (lock_dir / "owner").write_text("pid=1 held")
    try:
        r = _run_deploy(env)
        assert r.returncode == 3
        assert "another deployment holds the lock" in (r.stdout + r.stderr)
    finally:
        shutil.rmtree(lock_dir, ignore_errors=True)
