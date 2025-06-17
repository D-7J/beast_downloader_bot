#!/usr/bin/env python3
"""
اسکریپت مدیریت بات دانلودر
"""

import os
import sys
import asyncio
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# اضافه کردن root پروژه به path
sys.path.append(str(Path(__file__).parent.parent))

from src.database.mongo_client import mongo_manager
from src.database.redis_client import redis_manager
from src.database.models import User, SubscriptionType
from src.config import bot_config
from src.utils.helpers import format_file_size

class BotManager:
    """کلاس مدیریت بات"""
    
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
    async def connect_databases(self):
        """اتصال به دیتابیس‌ها"""
        await mongo_manager.connect()
        await redis_manager.connect()
        print("✅ Connected to databases")
    
    async def disconnect_databases(self):
        """قطع اتصال دیتابیس‌ها"""
        await mongo_manager.disconnect()
        await redis_manager.disconnect()
    
    # ==================== User Management ====================
    
    async def list_users(self, limit: int = 10, subscription: str = None):
        """لیست کاربران"""
        query = {}
        if subscription:
            query['subscription'] = subscription
        
        users = await mongo_manager.db.users.find(query).limit(limit).to_list(None)
        
        print(f"\n📋 Users List (Total: {len(users)})")
        print("-" * 80)
        print(f"{'ID':^12} | {'Name':^20} | {'Username':^15} | {'Subscription':^12} | {'Downloads':^10}")
        print("-" * 80)
        
        for user in users:
            print(f"{user['user_id']:^12} | {user.get('first_name', 'N/A')[:20]:^20} | "
                  f"@{user.get('username', 'N/A')[:14]:^15} | {user['subscription']:^12} | "
                  f"{user.get('total_downloads', 0):^10}")
    
    async def add_premium(self, user_id: int, subscription_type: str, days: int = 30):
        """اضافه کردن اشتراک پرمیوم"""
        try:
            user = await mongo_manager.get_user(user_id)
            if not user:
                print(f"❌ User {user_id} not found!")
                return
            
            sub_type = SubscriptionType(subscription_type)
            success = await mongo_manager.update_subscription(user_id, sub_type, days)
            
            if success:
                print(f"✅ Successfully added {subscription_type} subscription for {days} days to user {user_id}")
            else:
                print(f"❌ Failed to update subscription")
                
        except ValueError:
            print(f"❌ Invalid subscription type: {subscription_type}")
            print(f"Valid types: {', '.join([s.value for s in SubscriptionType])}")
    
    async def ban_user(self, user_id: int, reason: str = "Admin action"):
        """مسدود کردن کاربر"""
        success = await mongo_manager.ban_user(user_id, reason)
        if success:
            print(f"✅ User {user_id} banned successfully")
        else:
            print(f"❌ Failed to ban user {user_id}")
    
    async def unban_user(self, user_id: int):
        """رفع مسدودیت کاربر"""
        result = await mongo_manager.db.users.update_one(
            {'user_id': user_id},
            {'$set': {'is_banned': False, 'ban_reason': None}}
        )
        
        if result.modified_count > 0:
            print(f"✅ User {user_id} unbanned successfully")
        else:
            print(f"❌ Failed to unban user {user_id}")
    
    # ==================== Statistics ====================
    
    async def show_stats(self):
        """نمایش آمار کلی"""
        stats = await mongo_manager.get_dashboard_stats()
        
        print("\n📊 Bot Statistics")
        print("=" * 50)
        print(f"👥 Total Users: {stats['total_users']:,}")
        print(f"🟢 Active Users (7 days): {stats['active_users']:,}")
        print(f"📥 Total Downloads: {stats['total_downloads']:,}")
        print(f"📅 Today's Downloads: {stats['today_downloads']:,}")
        print(f"💰 Monthly Revenue: {stats['monthly_revenue']:,} IRR")
        print("\n📊 Subscription Distribution:")
        
        for sub_type, count in stats['subscription_stats'].items():
            percentage = (count / stats['total_users'] * 100) if stats['total_users'] > 0 else 0
            print(f"  • {sub_type}: {count:,} ({percentage:.1f}%)")
    
    async def revenue_report(self, days: int = 30):
        """گزارش درآمد"""
        start_date = datetime.now() - timedelta(days=days)
        
        pipeline = [
            {
                '$match': {
                    'status': 'paid',
                    'paid_at': {'$gte': start_date}
                }
            },
            {
                '$group': {
                    '_id': {
                        'date': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$paid_at'}},
                        'subscription': '$subscription_type'
                    },
                    'count': {'$sum': 1},
                    'revenue': {'$sum': '$amount'}
                }
            },
            {
                '$sort': {'_id.date': -1}
            }
        ]
        
        results = await mongo_manager.db.payments.aggregate(pipeline).to_list(None)
        
        print(f"\n💰 Revenue Report (Last {days} days)")
        print("=" * 60)
        print(f"{'Date':^12} | {'Plan':^10} | {'Count':^8} | {'Revenue (IRR)':^15}")
        print("-" * 60)
        
        total_revenue = 0
        for item in results:
            date = item['_id']['date']
            plan = item['_id']['subscription']
            count = item['count']
            revenue = item['revenue']
            total_revenue += revenue
            
            print(f"{date:^12} | {plan:^10} | {count:^8} | {revenue:>15,}")
        
        print("-" * 60)
        print(f"{'TOTAL':^32} | {total_revenue:>15,}")
    
    # ==================== Maintenance ====================
    
    async def cleanup_database(self, days: int = 30):
        """پاکسازی دیتابیس"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # حذف دانلودهای قدیمی
        result = await mongo_manager.db.downloads.delete_many({
            'created_at': {'$lt': cutoff_date},
            'status': {'$in': ['completed', 'failed', 'cancelled']}
        })
        
        print(f"✅ Deleted {result.deleted_count} old download records")
        
        # حذف کش Redis
        keys = await redis_manager.client.keys("*")
        if keys:
            deleted = await redis_manager.client.delete(*keys)
            print(f"✅ Cleared {deleted} Redis cache keys")
    
    async def backup_database(self, output_dir: str = "./backups"):
        """بکاپ از دیتابیس"""
        from src.tasks.maintenance_tasks import _backup_database_async
        
        print("📦 Creating database backup...")
        result = await _backup_database_async()
        
        if result['success']:
            print(f"✅ Backup created successfully")
            print(f"📁 File: {result['file_path']}")
            print(f"📊 Records: {result['records']:,}")
            print(f"💾 Size: {format_file_size(result['size'])}")
        else:
            print("❌ Backup failed!")
    
    async def migrate_database(self):
        """مهاجرت دیتابیس به نسخه جدید"""
        print("🔄 Starting database migration...")
        
        # اینجا می‌توانید migration scripts اضافه کنید
        # مثال: اضافه کردن فیلد جدید به همه کاربران
        
        result = await mongo_manager.db.users.update_many(
            {'settings': {'$exists': False}},
            {'$set': {'settings': {}}}
        )
        
        print(f"✅ Updated {result.modified_count} users")
        print("✅ Migration completed")
    
    # ==================== Testing ====================
    
    async def send_test_message(self, user_id: int, message: str):
        """ارسال پیام تست"""
        from telegram import Bot
        
        try:
            bot = Bot(token=bot_config.token)
            await bot.send_message(chat_id=user_id, text=message)
            print(f"✅ Message sent to {user_id}")
        except Exception as e:
            print(f"❌ Failed to send message: {str(e)}")
    
    async def test_download(self, url: str):
        """تست دانلود"""
        from src.services.downloader import VideoDownloader
        from src.services.validator import URLValidator
        
        print(f"🔄 Testing download for: {url}")
        
        # اعتبارسنجی
        validator = URLValidator()
        is_valid, platform, clean_url = validator.validate_and_clean(url)
        
        if not is_valid:
            print(f"❌ Invalid URL")
            return
        
        print(f"✅ Platform: {platform}")
        print(f"✅ Clean URL: {clean_url}")
        
        # دریافت اطلاعات
        downloader = VideoDownloader()
        info = await downloader.get_video_info(clean_url, platform)
        
        if info:
            print(f"✅ Title: {info['title']}")
            print(f"✅ Duration: {info['duration']} seconds")
            print(f"✅ Formats: {len(info['formats'])}")
        else:
            print("❌ Failed to get video info")
    
    # ==================== Main ====================
    
    def run_command(self, func, *args, **kwargs):
        """اجرای دستور async"""
        try:
            self.loop.run_until_complete(self.connect_databases())
            result = self.loop.run_until_complete(func(*args, **kwargs))
            return result
        except KeyboardInterrupt:
            print("\n⚠️ Operation cancelled")
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            self.loop.run_until_complete(self.disconnect_databases())

def main():
    """تابع اصلی"""
    parser = argparse.ArgumentParser(description="Bot Management Script")
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # User commands
    user_parser = subparsers.add_parser('user', help='User management')
    user_subparsers = user_parser.add_subparsers(dest='user_command')
    
    # List users
    list_parser = user_subparsers.add_parser('list', help='List users')
    list_parser.add_argument('--limit', type=int, default=10, help='Number of users to show')
    list_parser.add_argument('--subscription', help='Filter by subscription type')
    
    # Add premium
    premium_parser = user_subparsers.add_parser('premium', help='Add premium subscription')
    premium_parser.add_argument('user_id', type=int, help='User ID')
    premium_parser.add_argument('type', choices=['bronze', 'silver', 'gold'], help='Subscription type')
    premium_parser.add_argument('--days', type=int, default=30, help='Duration in days')
    
    # Ban/Unban
    ban_parser = user_subparsers.add_parser('ban', help='Ban user')
    ban_parser.add_argument('user_id', type=int, help='User ID')
    ban_parser.add_argument('--reason', default='Admin action', help='Ban reason')
    
    unban_parser = user_subparsers.add_parser('unban', help='Unban user')
    unban_parser.add_argument('user_id', type=int, help='User ID')
    
    # Stats commands
    stats_parser = subparsers.add_parser('stats', help='Show statistics')
    
    # Revenue
    revenue_parser = subparsers.add_parser('revenue', help='Revenue report')
    revenue_parser.add_argument('--days', type=int, default=30, help='Number of days')
    
    # Maintenance
    cleanup_parser = subparsers.add_parser('cleanup', help='Cleanup database')
    cleanup_parser.add_argument('--days', type=int, default=30, help='Delete records older than N days')
    
    backup_parser = subparsers.add_parser('backup', help='Backup database')
    
    migrate_parser = subparsers.add_parser('migrate', help='Migrate database')
    
    # Testing
    test_parser = subparsers.add_parser('test', help='Testing commands')
    test_subparsers = test_parser.add_subparsers(dest='test_command')
    
    message_parser = test_subparsers.add_parser('message', help='Send test message')
    message_parser.add_argument('user_id', type=int, help='User ID')
    message_parser.add_argument('message', help='Message text')
    
    download_parser = test_subparsers.add_parser('download', help='Test download')
    download_parser.add_argument('url', help='Video URL')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    manager = BotManager()
    
    # Execute commands
    if args.command == 'user':
        if args.user_command == 'list':
            manager.run_command(manager.list_users, args.limit, args.subscription)
        elif args.user_command == 'premium':
            manager.run_command(manager.add_premium, args.user_id, args.type, args.days)
        elif args.user_command == 'ban':
            manager.run_command(manager.ban_user, args.user_id, args.reason)
        elif args.user_command == 'unban':
            manager.run_command(manager.unban_user, args.user_id)
        else:
            user_parser.print_help()
    
    elif args.command == 'stats':
        manager.run_command(manager.show_stats)
    
    elif args.command == 'revenue':
        manager.run_command(manager.revenue_report, args.days)
    
    elif args.command == 'cleanup':
        manager.run_command(manager.cleanup_database, args.days)
    
    elif args.command == 'backup':
        manager.run_command(manager.backup_database)
    
    elif args.command == 'migrate':
        manager.run_command(manager.migrate_database)
    
    elif args.command == 'test':
        if args.test_command == 'message':
            manager.run_command(manager.send_test_message, args.user_id, args.message)
        elif args.test_command == 'download':
            manager.run_command(manager.test_download, args.url)
        else:
            test_parser.print_help()

if __name__ == "__main__":
    main()