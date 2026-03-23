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
        },
    }
)
celery.autodiscover_tasks(["app.worker"])
