import os
import json
import asyncio
import zipfile
from datetime import datetime, timedelta
from typing import Dict, Any
from loguru import logger

from .celery_app import celery_app
from ..database.mongo_client import mongo_manager
from ..database.redis_client import redis_manager
from ..database.models import SubscriptionType, DownloadStatus
from ..config import download_config, bot_config
from ..utils.helpers import cleanup_old_files, get_directory_size, format_file_size

@celery_app.task(name='tasks.maintenance_tasks.cleanup_old_downloads')
def cleanup_old_downloads():
    """پاکسازی دانلودهای قدیمی"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(_cleanup_old_downloads_async())
        return result
    finally:
        loop.close()

async def _cleanup_old_downloads_async():
    """پاکسازی async دانلودها"""
    logger.info("Starting cleanup of old downloads")
    
    # پاکسازی فایل‌های فیزیکی
    files_deleted = await cleanup_old_files(
        download_config.download_dir,
        hours=download_config.cleanup_after_hours
    )
    
    temp_files_deleted = await cleanup_old_files(
        download_config.temp_dir,
        hours=24  # فایل‌های موقت بعد از 24 ساعت
    )
    
    # پاکسازی رکوردهای دیتابیس
    db_records_deleted = await mongo_manager.cleanup_old_downloads(
        hours=download_config.cleanup_after_hours * 2  # نگهداری رکورد برای مدت بیشتر
    )
    
    # پاکسازی کش Redis
    redis_keys_deleted = await _cleanup_redis_cache()
    
    # گزارش
    report = {
        'files_deleted': files_deleted,
        'temp_files_deleted': temp_files_deleted,
        'db_records_deleted': db_records_deleted,
        'redis_keys_deleted': redis_keys_deleted,
        'timestamp': datetime.now().isoformat()
    }
    
    logger.info(f"Cleanup completed: {json.dumps(report)}")
    
    # ارسال گزارش به ادمین‌ها
    await _send_admin_report(
        "🧹 گزارش پاکسازی",
        f"• فایل‌های حذف شده: {files_deleted}\n"
        f"• فایل‌های موقت: {temp_files_deleted}\n"
        f"• رکوردهای دیتابیس: {db_records_deleted}\n"
        f"• کلیدهای Redis: {redis_keys_deleted}"
    )
    
    return report

async def _cleanup_redis_cache():
    """پاکسازی کش Redis"""
    patterns = [
        "video_info:*",
        "download_link:*",
        "last_update:*",
        "stats:platform:*"
    ]
    
    total_deleted = 0
    
    for pattern in patterns:
        keys = await redis_manager.client.keys(pattern)
        if keys:
            deleted = await redis_manager.client.delete(*keys)
            total_deleted += deleted
    
    return total_deleted

@celery_app.task(name='tasks.maintenance_tasks.update_daily_statistics')
def update_daily_statistics():
    """بروزرسانی آمار روزانه"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(_update_daily_statistics_async())
        return result
    finally:
        loop.close()

async def _update_daily_statistics_async():
    """محاسبه و ذخیره آمار روزانه"""
    logger.info("Updating daily statistics")
    
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)
    
    # محاسبه آمار دیروز
    stats = {
        'date': yesterday,
        'total_users': await mongo_manager.db.users.count_documents({}),
        'new_users': await mongo_manager.db.users.count_documents({
            'joined_at': {'$gte': yesterday, '$lt': today}
        }),
        'active_users': await mongo_manager.db.users.count_documents({
            'last_activity': {'$gte': yesterday, '$lt': today}
        }),
        'total_downloads': await mongo_manager.db.downloads.count_documents({
            'created_at': {'$gte': yesterday, '$lt': today}
        }),
        'successful_downloads': await mongo_manager.db.downloads.count_documents({
            'created_at': {'$gte': yesterday, '$lt': today},
            'status': DownloadStatus.COMPLETED.value
        }),
        'failed_downloads': await mongo_manager.db.downloads.count_documents({
            'created_at': {'$gte': yesterday, '$lt': today},
            'status': DownloadStatus.FAILED.value
        })
    }
    
    # محاسبه حجم کل
    pipeline = [
        {
            '$match': {
                'created_at': {'$gte': yesterday, '$lt': today},
                'status': DownloadStatus.COMPLETED.value
            }
        },
        {
            '$group': {
                '_id': None,
                'total_size': {'$sum': '$file_size'}
            }
        }
    ]
    
    size_result = await mongo_manager.db.downloads.aggregate(pipeline).to_list(1)
    stats['total_size'] = size_result[0]['total_size'] if size_result else 0
    
    # آمار پلتفرم‌ها
    platform_pipeline = [
        {
            '$match': {
                'created_at': {'$gte': yesterday, '$lt': today}
            }
        },
        {
            '$group': {
                '_id': '$platform',
                'count': {'$sum': 1}
            }
        }
    ]
    
    platform_results = await mongo_manager.db.downloads.aggregate(platform_pipeline).to_list(None)
    stats['platform_stats'] = {item['_id']: item['count'] for item in platform_results}
    
    # آمار اشتراک‌ها
    subscription_stats = {}
    for sub_type in SubscriptionType:
        count = await mongo_manager.db.users.count_documents({
            'subscription': sub_type.value,
            'last_activity': {'$gte': yesterday}
        })
        subscription_stats[sub_type.value] = count
    stats['subscription_stats'] = subscription_stats
    
    # درآمد روزانه
    revenue_pipeline = [
        {
            '$match': {
                'paid_at': {'$gte': yesterday, '$lt': today},
                'status': 'paid'
            }
        },
        {
            '$group': {
                '_id': None,
                'total': {'$sum': '$amount'}
            }
        }
    ]
    
    revenue_result = await mongo_manager.db.payments.aggregate(revenue_pipeline).to_list(1)
    stats['revenue'] = revenue_result[0]['total'] if revenue_result else 0
    
    # ذخیره در دیتابیس
    await mongo_manager.db.statistics.update_one(
        {'date': yesterday},
        {'$set': stats},
        upsert=True
    )
    
    logger.info(f"Daily statistics updated: {json.dumps(stats, default=str)}")
    
    # ارسال خلاصه به ادمین‌ها
    summary = f"""
📊 **آمار روزانه - {yesterday.strftime('%Y/%m/%d')}**

👥 **کاربران:**
• کل: {stats['total_users']:,}
• جدید: {stats['new_users']:,}
• فعال: {stats['active_users']:,}

📥 **دانلودها:**
• کل: {stats['total_downloads']:,}
• موفق: {stats['successful_downloads']:,}
• ناموفق: {stats['failed_downloads']:,}
• حجم: {format_file_size(stats['total_size'])}

💰 **درآمد:** {stats['revenue']:,} تومان
    """
    
    await _send_admin_report("📊 آمار روزانه", summary)
    
    return stats

@celery_app.task(name='tasks.maintenance_tasks.check_expired_subscriptions')
def check_expired_subscriptions():
    """بررسی اشتراک‌های منقضی شده"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(_check_expired_subscriptions_async())
        return result
    finally:
        loop.close()

async def _check_expired_subscriptions_async():
    """بررسی و مدیریت اشتراک‌های منقضی"""
    logger.info("Checking expired subscriptions")
    
    now = datetime.now()
    
    # یافتن اشتراک‌های منقضی شده
    expired_users = await mongo_manager.db.users.find({
        'subscription': {'$ne': SubscriptionType.FREE.value},
        'subscription_expires': {'$lte': now}
    }).to_list(None)
    
    expired_count = 0
    warning_count = 0
    
    for user in expired_users:
        # تغییر به اشتراک رایگان
        await mongo_manager.db.users.update_one(
            {'_id': user['_id']},
            {
                '$set': {
                    'subscription': SubscriptionType.FREE.value,
                    'subscription_expires': None
                }
            }
        )
        expired_count += 1
        
        # ارسال پیام به کاربر
        try:
            from telegram import Bot
            bot = Bot(token=bot_config.token)
            
            await bot.send_message(
                chat_id=user['user_id'],
                text="⏰ **اشتراک شما منقضی شد!**\n\n"
                     "اشتراک شما به پایان رسیده و حساب شما به حالت رایگان تغییر یافت.\n"
                     "برای تمدید از /subscription استفاده کنید.",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to notify user {user['user_id']}: {str(e)}")
    
    # یافتن اشتراک‌هایی که به زودی منقضی می‌شوند (3 روز مانده)
    warning_date = now + timedelta(days=3)
    
    expiring_soon = await mongo_manager.db.users.find({
        'subscription': {'$ne': SubscriptionType.FREE.value},
        'subscription_expires': {
            '$gt': now,
            '$lte': warning_date
        }
    }).to_list(None)
    
    for user in expiring_soon:
        days_left = (user['subscription_expires'] - now).days
        
        try:
            from telegram import Bot
            bot = Bot(token=bot_config.token)
            
            await bot.send_message(
                chat_id=user['user_id'],
                text=f"⏳ **اشتراک شما {days_left} روز دیگر تمام می‌شود!**\n\n"
                     f"برای تمدید و جلوگیری از قطع سرویس، از /subscription استفاده کنید.",
                parse_mode='Markdown'
            )
            warning_count += 1
        except Exception as e:
            logger.error(f"Failed to warn user {user['user_id']}: {str(e)}")
    
    report = {
        'expired_count': expired_count,
        'warning_count': warning_count,
        'timestamp': datetime.now().isoformat()
    }
    
    logger.info(f"Subscription check completed: {json.dumps(report)}")
    
    if expired_count > 0 or warning_count > 0:
        await _send_admin_report(
            "🔔 بررسی اشتراک‌ها",
            f"• منقضی شده: {expired_count}\n"
            f"• هشدار ارسال شده: {warning_count}"
        )
    
    return report

@celery_app.task(name='tasks.maintenance_tasks.backup_database')
def backup_database():
    """ایجاد بکاپ از دیتابیس"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(_backup_database_async())
        return result
    finally:
        loop.close()

async def _backup_database_async():
    """ایجاد بکاپ async"""
    logger.info("Starting database backup")
    
    backup_dir = os.path.join(os.path.dirname(download_config.download_dir), 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f"backup_{timestamp}.json"
    backup_path = os.path.join(backup_dir, backup_filename)
    
    backup_data = {
        'timestamp': datetime.now().isoformat(),
        'version': '1.0',
        'collections': {}
    }
    
    # بکاپ از collections
    collections = ['users', 'downloads', 'payments', 'statistics']
    total_records = 0
    
    for collection_name in collections:
        collection = mongo_manager.db[collection_name]
        documents = await collection.find({}).to_list(None)
        
        # تبدیل ObjectId به string
        for doc in documents:
            if '_id' in doc:
                doc['_id'] = str(doc['_id'])
            # تبدیل datetime objects
            for key, value in doc.items():
                if isinstance(value, datetime):
                    doc[key] = value.isoformat()
        
        backup_data['collections'][collection_name] = documents
        total_records += len(documents)
    
    # ذخیره به فایل JSON
    with open(backup_path, 'w', encoding='utf-8') as f:
        json.dump(backup_data, f, ensure_ascii=False, indent=2)
    
    # فشرده‌سازی
    zip_filename = f"backup_{timestamp}.zip"
    zip_path = os.path.join(backup_dir, zip_filename)
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(backup_path, backup_filename)
    
    # حذف فایل JSON
    os.remove(backup_path)
    
    # محاسبه حجم
    file_size = os.path.getsize(zip_path)
    
    # پاکسازی بکاپ‌های قدیمی (نگهداری 7 روز)
    await _cleanup_old_backups(backup_dir, days=7)
    
    result = {
        'success': True,
        'file_path': zip_path,
        'size': file_size,
        'records': total_records,
        'timestamp': datetime.now().isoformat()
    }
    
    logger.info(f"Backup completed: {json.dumps(result)}")
    
    # ارسال به ادمین‌ها
    await _send_admin_report(
        "💾 بکاپ دیتابیس",
        f"✅ بکاپ با موفقیت ایجاد شد\n"
        f"📦 حجم: {format_file_size(file_size)}\n"
        f"📊 رکوردها: {total_records:,}"
    )
    
    return result

async def _cleanup_old_backups(backup_dir: str, days: int):
    """حذف بکاپ‌های قدیمی"""
    cutoff_date = datetime.now() - timedelta(days=days)
    
    for filename in os.listdir(backup_dir):
        if filename.startswith('backup_') and filename.endswith('.zip'):
            filepath = os.path.join(backup_dir, filename)
            file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
            
            if file_time < cutoff_date:
                os.remove(filepath)
                logger.info(f"Deleted old backup: {filename}")

@celery_app.task(name='tasks.maintenance_tasks.optimize_database')
def optimize_database():
    """بهینه‌سازی دیتابیس"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(_optimize_database_async())
        return result
    finally:
        loop.close()

async def _optimize_database_async():
    """بهینه‌سازی async دیتابیس"""
    logger.info("Starting database optimization")
    
    # بازسازی ایندکس‌ها
    collections = ['users', 'downloads', 'payments']
    
    for collection_name in collections:
        collection = mongo_manager.db[collection_name]
        await collection.reindex()
    
    # پاکسازی رکوردهای تکراری یا ناقص
    # حذف دانلودهای بدون user_id
    deleted = await mongo_manager.db.downloads.delete_many({'user_id': None})
    logger.info(f"Deleted {deleted.deleted_count} invalid download records")
    
    # آنالیز و بهینه‌سازی
    stats = await mongo_manager.db.command('dbStats')
    
    result = {
        'success': True,
        'collections_optimized': len(collections),
        'invalid_records_deleted': deleted.deleted_count,
        'db_size': stats['dataSize'],
        'timestamp': datetime.now().isoformat()
    }
    
    logger.info(f"Database optimization completed: {json.dumps(result)}")
    
    return result

async def _send_admin_report(title: str, message: str):
    """ارسال گزارش به ادمین‌ها"""
    try:
        from telegram import Bot
        bot = Bot(token=bot_config.token)
        
        for admin_id in bot_config.admin_ids:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=f"🤖 **{title}**\n\n{message}\n\n"
                         f"⏰ {datetime.now().strftime('%Y/%m/%d %H:%M')}",
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Failed to send report to admin {admin_id}: {str(e)}")
                
    except Exception as e:
        logger.error(f"Failed to send admin reports: {str(e)}")

@celery_app.task(name='tasks.maintenance_tasks.monitor_system_health')
def monitor_system_health():
    """مانیتور سلامت سیستم"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(_monitor_system_health_async())
        return result
    finally:
        loop.close()

async def _monitor_system_health_async():
    """بررسی سلامت سیستم"""
    import psutil
    
    health_status = {
        'timestamp': datetime.now().isoformat(),
        'status': 'healthy',
        'issues': []
    }
    
    # بررسی CPU
    cpu_percent = psutil.cpu_percent(interval=1)
    if cpu_percent > 80:
        health_status['issues'].append(f"High CPU usage: {cpu_percent}%")
        health_status['status'] = 'warning'
    
    # بررسی RAM
    memory = psutil.virtual_memory()
    if memory.percent > 85:
        health_status['issues'].append(f"High memory usage: {memory.percent}%")
        health_status['status'] = 'warning'
    
    # بررسی دیسک
    disk = psutil.disk_usage('/')
    if disk.percent > 90:
        health_status['issues'].append(f"Low disk space: {100 - disk.percent}% free")
        health_status['status'] = 'critical'
    
    # بررسی اتصال به دیتابیس‌ها
    try:
        await mongo_manager.db.command('ping')
    except:
        health_status['issues'].append("MongoDB connection failed")
        health_status['status'] = 'critical'
    
    try:
        await redis_manager.client.ping()
    except:
        health_status['issues'].append("Redis connection failed")
        health_status['status'] = 'critical'
    
    # ارسال هشدار در صورت وجود مشکل
    if health_status['issues']:
        issues_text = '\n'.join(f"• {issue}" for issue in health_status['issues'])
        await _send_admin_report(
            f"⚠️ System Health Alert - {health_status['status'].upper()}",
            f"Issues detected:\n{issues_text}"
        )
    
    logger.info(f"System health check: {json.dumps(health_status)}")
    
    return health_status