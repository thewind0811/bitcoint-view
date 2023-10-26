from celery import Celery

app = Celery('DJANGO_SETTINGS_MODULE', 'backend.settings')

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks()

app.conf.beat_schedule = {}

