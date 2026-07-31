import threading

from redis import Redis
from rq import Queue

from app_services import run_generation_job
from app_settings import settings


def enqueue_generation(post_id: int):
    if settings.SYNC_JOBS:
        run_generation_job(post_id)
        return None

    # Prefer Redis/RQ when available; fall back to an in-process background thread for local dev.
    try:
        redis_conn = Redis.from_url(settings.REDIS_URL)
        queue = Queue("generation", connection=redis_conn)
        return queue.enqueue(run_generation_job, post_id)
    except Exception:
        t = threading.Thread(target=run_generation_job, args=(post_id,), daemon=True)
        t.start()
        return {"mode": "thread"}
