from pathlib import Path

from dotenv import load_dotenv

# Load .env before saas_settings so BASE_DIR & co. match the API process.
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

from redis import Redis
from rq import Worker

from saas_settings import settings


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    # Content Factory auto-generation scheduler (daemon thread; kill switch
    # FACTORY_SCHEDULER_ENABLED=false). One instance, only in the worker.
    try:
        import scheduler
        scheduler.start_in_background()
    except Exception as exc:  # never let the scheduler stop the worker
        logging.getLogger("factory.scheduler").warning("scheduler not started: %s", exc)
    # Daily long-form autopilot (separate cadence, memory-safe pipeline; kill
    # switch LONGFORM_SCHEDULER_ENABLED=false). Opt-in per channel.
    try:
        import longform_scheduler
        longform_scheduler.start_in_background()
    except Exception as exc:  # never let it stop the worker
        logging.getLogger("longform.scheduler").warning("longform scheduler not started: %s", exc)
    redis_conn = Redis.from_url(settings.REDIS_URL)
    worker = Worker(["generation", "render"], connection=redis_conn)
    worker.work()
