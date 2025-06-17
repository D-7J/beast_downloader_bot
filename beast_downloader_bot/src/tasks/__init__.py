"""
Celery tasks for asynchronous processing
"""

from .celery_app import celery_app
from .download_tasks import (
    process_download_task,
    retry_failed_downloads,
    cancel_download
)
from .maintenance_tasks import (
    cleanup_old_downloads,
    update_daily_statistics,
    check_expired_subscriptions,
    backup_database,
    optimize_database,
    monitor_system_health
)

__all__ = [
    'celery_app',
    'process_download_task',
    'retry_failed_downloads',
    'cancel_download',
    'cleanup_old_downloads',
    'update_daily_statistics',
    'check_expired_subscriptions',
    'backup_database',
    'optimize_database',
    'monitor_system_health'
]