from celery import Celery

from app.config import settings

celery = Celery("uyt")
celery.config_from_object(
    {
        "broker_url": settings.redis_url,
        "result_backend": settings.redis_url.replace("/0", "/1"),
        "task_serializer": "json",
        "result_serializer": "json",
        "accept_content": ["json"],
        "task_track_started": True,
        "task_acks_late": True,
        "worker_prefetch_multiplier": 1,
        "broker_connection_retry_on_startup": True,
        "broker_connection_retry": True,
        "broker_connection_max_retries": 10,
        "task_routes": {
            "app.worker.tasks.run_probe": {"queue": "probe"},
            "app.worker.tasks.run_stage": {"queue": "download"},
            "app.worker.tasks.check_subscription": {"queue": "probe"},
            "app.worker.tasks.check_all_subscriptions": {"queue": "probe"},
            "app.worker.tasks.run_compilation": {"queue": "download"},
        },
        "beat_schedule": {
            "check-subscriptions": {
                "task": "app.worker.tasks.check_all_subscriptions",
                "schedule": 300.0,  # every 5 minutes
            },
            "storage-cleanup": {
                "task": "app.worker.tasks.run_storage_cleanup",
                "schedule": 3600.0,  # every hour
            },
        },
    }
)
celery.autodiscover_tasks(["app.worker"])
