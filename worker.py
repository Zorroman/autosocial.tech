from pathlib import Path

from dotenv import load_dotenv

# Load .env before saas_settings so BASE_DIR & co. match the API process.
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

from redis import Redis
from rq import Worker

from saas_settings import settings


if __name__ == "__main__":
    redis_conn = Redis.from_url(settings.REDIS_URL)
    worker = Worker(["generation", "render"], connection=redis_conn)
    worker.work()
