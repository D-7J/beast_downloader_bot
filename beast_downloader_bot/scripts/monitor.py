#!/usr/bin/env python3
"""
اسکریپت مانیتورینگ real-time بات
"""

import asyncio
import sys
import signal
from datetime import datetime
from pathlib import Path
import psutil
import humanize
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.layout import Layout
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

# اضافه کردن root پروژه به path
sys.path.append(str(Path(__file__).parent.parent))

from src.database.mongo_client import mongo_manager
from src.database.redis_client import redis_manager
from src.config import bot_config

console = Console()

class BotMonitor:
    """کلاس مانیتورینگ بات"""
    
    def __init__(self):
        self.running = True
        self.console = Console()
        
    async def connect(self):
        """اتصال به دیتابیس‌ها"""
        await mongo_manager.connect()
        await redis_manager.connect()
    
    async def disconnect(self):
        """قطع اتصال"""
        await mongo_manager.disconnect()
        await redis_manager.disconnect()
    
    def handle_signal(self, signum, frame):
        """مدیریت سیگنال‌ها"""
        self.running = False
        console.print("\n[yellow]Stopping monitor...[/yellow]")
    
    async def get_system_stats(self) -> dict:
        """دریافت آمار سیستم"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Network I/O
        net_io = psutil.net_io_counters()
        
        return {
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent,
            'memory_used': humanize.naturalsize(memory.used),
            'memory_total': humanize.naturalsize(memory.total),
            'disk_percent': disk.percent,
            'disk_free': humanize.naturalsize(disk.free),
            'disk_total': humanize.naturalsize(disk.total),
            'network_sent': humanize.naturalsize(net_io.bytes_sent),
            'network_recv': humanize.naturalsize(net_io.bytes_recv),
        }
    
    async def get_bot_stats(self) -> dict:
        """دریافت آمار بات"""
        # آمار کلی
        stats = await mongo_manager.get_dashboard_stats()
        
        # کاربران آنلاین
        online_users = await redis_manager.get_active_users_count()
        
        # صف‌ها
        queue_stats = await redis_manager.get_queue_stats()
        
        # دانلودهای فعال
        active_downloads = await mongo_manager.db.downloads.count_documents({
            'status': {'$in': ['pending', 'processing']}
        })
        
        # آمار امروز
        today_stats = await self.get_today_stats()
        
        return {
            **stats,
            'online_users': online_users,
            'queue_stats': queue_stats,
            'active_downloads': active_downloads,
            **today_stats
        }
    
    async def get_today_stats(self) -> dict:
        """آمار امروز"""
        from datetime import datetime, time
        
        today_start = datetime.combine(datetime.now().date(), time.min)
        
        # دانلودهای امروز به تفکیک ساعت
        pipeline = [
            {
                '$match': {
                    'created_at': {'$gte': today_start}
                }
            },
            {
                '$group': {
                    '_id': {
                        '$hour': '$created_at'
                    },
                    'count': {'$sum': 1}
                }
            },
            {
                '$sort': {'_id': 1}
            }
        ]
        
        hourly_downloads = await mongo_manager.db.downloads.aggregate(pipeline).to_list(None)
        
        # ایجاد آرایه 24 ساعته
        hourly_data = [0] * 24
        for item in hourly_downloads:
            hour = item['_id']
            count = item['count']
            hourly_data[hour] = count
        
        return {
            'hourly_downloads': hourly_data,
            'peak_hour': hourly_data.index(max(hourly_data)) if hourly_data else 0
        }
    
    async def get_recent_activities(self, limit: int = 10) -> list:
        """فعالیت‌های اخیر"""
        # دانلودهای اخیر
        downloads = await mongo_manager.db.downloads.find({}).sort('created_at', -1).limit(limit).to_list(None)
        
        activities = []
        for dl in downloads:
            activities.append({
                'type': 'download',
                'user_id': dl['user_id'],
                'platform': dl['platform'],
                'status': dl['status'],
                'time': dl['created_at']
            })
        
        return activities
    
    def create_dashboard(self, system_stats: dict, bot_stats: dict, activities: list) -> Layout:
        """ایجاد داشبورد"""
        layout = Layout()
        
        # تقسیم صفحه
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3)
        )
        
        # Header
        header_text = f"[bold cyan]Persian Downloader Bot Monitor[/bold cyan] - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        layout["header"].update(Panel(header_text, style="cyan"))
        
        # Body
        layout["body"].split_row(
            Layout(name="stats", ratio=2),
            Layout(name="system", ratio=1)
        )
        
        # آمار بات
        stats_table = Table(title="📊 Bot Statistics", expand=True)
        stats_table.add_column("Metric", style="cyan")
        stats_table.add_column("Value", style="green")
        
        stats_table.add_row("Total Users", f"{bot_stats['total_users']:,}")
        stats_table.add_row("Online Users", f"{bot_stats['online_users']:,}")
        stats_table.add_row("Active Downloads", f"{bot_stats['active_downloads']:,}")
        stats_table.add_row("Today Downloads", f"{bot_stats['today_downloads']:,}")
        stats_table.add_row("Monthly Revenue", f"{bot_stats['monthly_revenue']:,} IRR")
        
        # صف‌ها
        for queue_name, count in bot_stats['queue_stats'].items():
            stats_table.add_row(f"Queue {queue_name}", str(count))
        
        layout["stats"].update(Panel(stats_table))
        
        # آمار سیستم
        system_table = Table(title="💻 System Stats", expand=True)
        system_table.add_column("Resource", style="yellow")
        system_table.add_column("Usage", style="magenta")
        
        # CPU با progress bar
        cpu_bar = self.create_progress_bar(system_stats['cpu_percent'])
        system_table.add_row("CPU", f"{cpu_bar} {system_stats['cpu_percent']}%")
        
        # Memory
        mem_bar = self.create_progress_bar(system_stats['memory_percent'])
        system_table.add_row("Memory", f"{mem_bar} {system_stats['memory_used']}/{system_stats['memory_total']}")
        
        # Disk
        disk_bar = self.create_progress_bar(system_stats['disk_percent'])
        system_table.add_row("Disk", f"{disk_bar} {system_stats['disk_free']} free")
        
        # Network
        system_table.add_row("Network ↑", system_stats['network_sent'])
        system_table.add_row("Network ↓", system_stats['network_recv'])
        
        layout["system"].update(Panel(system_table))
        
        # Footer - فعالیت‌های اخیر
        activities_text = "Recent Activities: "
        for act in activities[:5]:
            status_emoji = "✅" if act['status'] == 'completed' else "⏳"
            activities_text += f"{status_emoji} {act['platform']} "
        
        layout["footer"].update(Panel(activities_text, style="dim"))
        
        return layout
    
    def create_progress_bar(self, percentage: float, width: int = 20) -> str:
        """ایجاد progress bar"""
        filled = int(width * percentage / 100)
        bar = "█" * filled + "░" * (width - filled)
        
        # رنگ بر اساس مقدار
        if percentage < 50:
            color = "green"
        elif percentage < 80:
            color = "yellow"
        else:
            color = "red"
        
        return f"[{color}]{bar}[/{color}]"
    
    async def run(self):
        """اجرای مانیتور"""
        # ثبت signal handlers
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)
        
        console.print("[green]Starting Bot Monitor...[/green]")
        
        try:
            await self.connect()
            console.print("[green]Connected to databases[/green]")
            
            with Live(console=console, refresh_per_second=1) as live:
                while self.running:
                    try:
                        # دریافت آمار
                        system_stats = await self.get_system_stats()
                        bot_stats = await self.get_bot_stats()
                        activities = await self.get_recent_activities()
                        
                        # ایجاد و نمایش داشبورد
                        dashboard = self.create_dashboard(system_stats, bot_stats, activities)
                        live.update(dashboard)
                        
                        # صبر برای refresh بعدی
                        await asyncio.sleep(2)
                        
                    except Exception as e:
                        console.print(f"[red]Error: {str(e)}[/red]")
                        await asyncio.sleep(5)
                        
        except KeyboardInterrupt:
            console.print("\n[yellow]Monitor stopped by user[/yellow]")
        finally:
            await self.disconnect()
            console.print("[green]Disconnected from databases[/green]")

async def main():
    """تابع اصلی"""
    monitor = BotMonitor()
    await monitor.run()

if __name__ == "__main__":
    # بررسی وابستگی‌ها
    try:
        import rich
    except ImportError:
        print("Please install rich: pip install rich")
        sys.exit(1)
    
    # اجرا
    asyncio.run(main())