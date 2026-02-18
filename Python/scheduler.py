from apscheduler.schedulers.background import BackgroundScheduler
from flask import current_app
import requests

def post_job():
    with current_app.app_context():
        # This is a mock — in реальном проекте данные берутся из базы
        requests.post("http://localhost:5000/generate-and-post", json={
            "niche": "маркетинг"
        })

def init_scheduler(app):
    scheduler = BackgroundScheduler()
    scheduler.add_job(post_job, 'cron', hour=9)  # ⏰ Постим каждый день в 9:00
    scheduler.start()
