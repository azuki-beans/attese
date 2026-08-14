import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("attese")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Aggiorna i dati ogni giorno alle 06:00
app.conf.beat_schedule = {
    "fetch-waitingtimes-daily": {
        "task": "attese.tasks.fetch_waitingtimes",
        "schedule": crontab(hour=6, minute=0),
    },
}
