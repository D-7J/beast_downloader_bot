from celery import Celery
from celery.schedules import crontab
from kombu import Queue, Exchange
from ..config import celery_config

# ایجاد Celery app
celery_app = Celery('downloader_bot')

# تنظیمات
celery_app.conf.update(
    broker_url=celery_config.broker_url,
    result_backend=celery_config.result_backend,
    
    # تنظیمات صف
    task_queues=(
        Queue('gold', Exchange('gold'), routing_key='gold', priority=10),
        Queue('silver', Exchange('silver'), routing_key='silver', priority=7),
        Queue('bronze', Exchange('bronze'), routing_key='bronze', priority=5),
        Queue('free', Exchange('free'), routing_key='free', priority=1),
        Queue('default', Exchange('default'), routing_key='default', priority=3),
    ),
    
    # مسیریابی
    task_routes={
        'tasks.download_tasks.process_download_task': {'queue': 'default'},
        'tasks.maintenance_tasks.*': {'queue': 'default'},
    },
    
    # تنظیمات عملکرد
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    
    # محدودیت زمانی
    task_time_limit=celery_config.task_time_limit,
    task_soft_time_limit=celery_config.task_soft_time_limit,
    
    # سریال‌سازی
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    
    # منطقه زمانی
    timezone='Asia/Tehran',
    enable_utc=True,
    
    # وظایف زمان‌بندی شده
    beat_schedule={
        'cleanup-old-downloads': {
            'task': 'tasks.maintenance_tasks.cleanup_old_downloads',
            'schedule': crontab(hour=3, minute=0),  # هر روز ساعت 3 صبح
        },
        'update-statistics': {
            'task': 'tasks.maintenance_tasks.update_daily_statistics',
            'schedule': crontab(hour=0, minute=5),  # هر روز 5 دقیقه بعد از نیمه‌شب
        },
        'check-expired-subscriptions': {
            'task': 'tasks.maintenance_tasks.check_expired_subscriptions',
            'schedule': crontab(hour='*/6'),  # هر 6 ساعت
        },
        'backup-database': {
            'task': 'tasks.maintenance_tasks.backup_database',
            'schedule': crontab(hour=4, minute=0, day_of_week=1),  # دوشنبه‌ها ساعت 4 صبح
        },
    },
)

# Auto-discovery tasks
celery_app.autodiscover_tasks(['src.tasks'])