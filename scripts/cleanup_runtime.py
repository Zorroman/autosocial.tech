"""Safe runtime cleanup for the video factory.

Dry-run by default: prints what WOULD be deleted. Nothing referenced by a
scene, project, publication, completed render job or active job is ever
touched. Execute only with an explicit flag:

    python scripts/cleanup_runtime.py            # dry-run preview
    python scripts/cleanup_runtime.py --execute  # actually delete

Targets:
- .tmp_* render work directories older than 1 day
- tts_preview_*.mp3 older than 7 days
- fixture clips in cache/fixture_clips not referenced by any scene
- stock clips in cache/footage not referenced by any scene (older than 30 days)
"""
import argparse
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

from database import SessionLocal  # noqa: E402
from saas_models import RenderJob, VideoProject, VideoScene  # noqa: E402
from saas_settings import settings  # noqa: E402

DAY = 86400


def referenced_paths(db) -> set[str]:
    refs: set[str] = set()
    for (p,) in db.query(VideoScene.selected_media_path).filter(VideoScene.selected_media_path.isnot(None)).all():
        refs.add(str(Path(p).resolve()))
    for (p,) in db.query(VideoProject.voiceover_path).filter(VideoProject.voiceover_path.isnot(None)).all():
        refs.add(str(Path(p).resolve()))
    for (p,) in db.query(VideoProject.output_path).filter(VideoProject.output_path.isnot(None)).all():
        refs.add(str((settings.BASE_DIR / p).resolve()))
    for (p,) in db.query(RenderJob.output_path).filter(RenderJob.output_path.isnot(None)).all():
        refs.add(str((settings.BASE_DIR / p).resolve()))
    return refs


def active_job_ids(db) -> set[int]:
    return {j.id for j in db.query(RenderJob).filter(RenderJob.status.in_(["pending", "processing"])).all()}


def collect_candidates(db):
    now = time.time()
    refs = referenced_paths(db)
    active = active_job_ids(db)
    candidates = []

    videos_dir = settings.OUTPUT_VIDEOS_DIR
    if videos_dir.exists():
        for d in videos_dir.glob(".tmp_*"):
            if not d.is_dir():
                continue
            if any(f".tmp_project_" in d.name and f"_job_{jid}" in d.name for jid in active):
                continue
            if now - d.stat().st_mtime > DAY:
                candidates.append(("tmp_render_dir", d))

    audio_dir = settings.OUTPUT_AUDIO_DIR
    if audio_dir.exists():
        for f in audio_dir.glob("tts_preview_*.mp3"):
            if now - f.stat().st_mtime > 7 * DAY and str(f.resolve()) not in refs:
                candidates.append(("tts_preview", f))

    fixtures_dir = settings.CACHE_DIR / "fixture_clips"
    if fixtures_dir.exists():
        for f in fixtures_dir.glob("*.mp4"):
            if str(f.resolve()) not in refs:
                candidates.append(("unused_fixture", f))

    footage_dir = settings.FOOTAGE_CACHE_DIR
    if footage_dir.exists():
        for f in footage_dir.rglob("*.mp4"):
            if str(f.resolve()) in refs:
                continue
            if now - f.stat().st_mtime > 30 * DAY:
                candidates.append(("old_stock", f))

    return candidates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="actually delete (default: dry-run)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        candidates = collect_candidates(db)
    finally:
        db.close()

    if not candidates:
        print("Nothing to clean up.")
        return

    total = 0
    for kind, path in candidates:
        size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) if path.is_dir() else path.stat().st_size
        total += size
        print(f"[{kind}] {path} ({size / 1024:.0f} KB)")
    print(f"\n{len(candidates)} items, {total / 1024 / 1024:.1f} MB total")

    if not args.execute:
        print("\nDRY-RUN: nothing deleted. Re-run with --execute to delete.")
        return

    confirm = input("Type 'delete' to confirm removal: ").strip()
    if confirm != "delete":
        print("Aborted.")
        return
    for kind, path in candidates:
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            print(f"deleted {path}")
        except OSError as exc:
            print(f"failed {path}: {exc}")


if __name__ == "__main__":
    main()
