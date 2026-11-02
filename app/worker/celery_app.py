from celery import Celery  # type: ignore[import-untyped]
from celery.schedules import crontab  # type: ignore[import-untyped]

from app.config import celery_settings

celery_app = Celery(
    "fastship",
    broker=celery_settings.CELERY_BROKER_URL,
    backend=celery_settings.CELERY_RESULT_BACKEND,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    # JSON is safe to read, pickle could run code from a bad message
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    # Remove a task from the queue only after it finishes, so a crash doesn't lose it
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Each worker process reserves one task at a time
    worker_prefetch_multiplier=1,
    # RabbitMQ confirms it stored each message
    broker_transport_options={"confirm_publish": True},
    # Don't let the API wait long if RabbitMQ is down
    task_publish_retry_policy={"max_retries": 1, "interval_start": 0},
    # RabbitMQ 4 rejects Celery's default temporary queues, these settings replace them
    control_queue_exclusive=True,
    event_queue_exclusive=True,
    broker_connection_retry_on_startup=True,
    # Remove results from Redis after a day
    result_expires=86400,
    # Events let Flower show what is happening
    worker_send_task_events=True,
    task_send_sent_event=True,
    task_track_started=True,
    # Celery Beat runs these on a schedule
    beat_schedule={
        "notify-overdue-shipments": {
            "task": "app.worker.tasks.notify_overdue_shipments",
            "schedule": crontab(hour=8, minute=0),
        },
    },
)