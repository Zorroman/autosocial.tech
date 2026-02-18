from redis import Redis
from rq import Worker

from saas_settings import settings


if __name__ == "__main__":
    redis_conn = Redis.from_url(settings.REDIS_URL)
    worker = Worker(["generation"], connection=redis_conn)
    worker.work()
