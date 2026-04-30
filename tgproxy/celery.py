import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tgproxy.settings")

app = Celery("tgproxy")

app.conf.broker_url = os.getenv("CELERY_BROKER_URL", "sqla+sqlite:///celerybroker.sqlite3")

app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()