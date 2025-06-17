"""
Health Check Handler برای مانیتورینگ سلامت بات
"""

import time
from datetime import datetime
from typing import Dict, Any
from aiohttp import web
import psutil
from loguru import logger

from ..database.mongo_client import mongo_manager
from ..database.redis_client import redis_manager
from ..config import bot_config
from ..version import __version__

class HealthCheckServer:
    """سرور Health Check"""
    
    def __init__(self, bot_instance=None):
        self.bot = bot_instance
        self.start_time = time.time()
        self.app = web.Application()
        self.setup_routes()
    
    def setup_routes(self):
        """تنظیم route ها"""
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/health/detailed', self.detailed_health_check)
        self.app.router.add_get('/metrics', self.metrics)
        self.app.router.add_get('/ready', self.readiness_check)
        self.app.router.add_get('/live', self.liveness_check)
    
    async def health_check(self, request):
        """بررسی سریع سلامت"""
        try:
            # بررسی اتصالات
            await mongo_manager.db.command('ping')
            await redis_manager.client.ping()
            
            return web.json_response({
                'status': 'healthy',
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return web.json_response({
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }, status=503)
    
    async def detailed_health_check(self, request):
        """بررسی دقیق سلامت"""
        health_data = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'version': __version__,
            'uptime': time.time() - self.start_time,
            'checks': {}
        }
        
        # بررسی MongoDB
        try:
            start = time.time()
            await mongo_manager.db.command('ping')
            health_data['checks']['mongodb'] = {
                'status': 'healthy',
                'response_time': time.time() - start
            }
        except Exception as e:
            health_data['checks']['mongodb'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            health_data['status'] = 'unhealthy'
        
        # بررسی Redis
        try:
            start = time.time()
            await redis_manager.client.ping()
            info = await redis_manager.client.info()
            health_data['checks']['redis'] = {
                'status': 'healthy',
                'response_time': time.time() - start,
                'connected_clients': info.get('connected_clients', 0),
                'used_memory': info.get('used_memory_human', 'unknown')
            }
        except Exception as e:
            health_data['checks']['redis'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            health_data['status'] = 'unhealthy'
        
        # بررسی Telegram Bot API
        if self.bot:
            try:
                start = time.time()
                bot_info = await self.bot.get_me()
                health_data['checks']['telegram_api'] = {
                    'status': 'healthy',
                    'response_time': time.time() - start,
                    'bot_username': bot_info.username
                }
            except Exception as e:
                health_data['checks']['telegram_api'] = {
                    'status': 'unhealthy',
                    'error': str(e)
                }
                health_data['status'] = 'unhealthy'
        
        # منابع سیستم
        health_data['system'] = {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent
        }
        
        # تعیین وضعیت HTTP
        status_code = 200 if health_data['status'] == 'healthy' else 503
        
        return web.json_response(health_data, status=status_code)
    
    async def metrics(self, request):
        """متریک‌ها برای Prometheus"""
        try:
            # دریافت آمار
            stats = await mongo_manager.get_dashboard_stats()
            active_users = await redis_manager.get_active_users_count()
            queue_stats = await redis_manager.get_queue_stats()
            
            # فرمت Prometheus
            metrics_text = f"""
# HELP bot_users_total Total number of users
# TYPE bot_users_total gauge
bot_users_total {stats['total_users']}

# HELP bot_users_active Active users in last 7 days
# TYPE bot_users_active gauge
bot_users_active {stats['active_users']}

# HELP bot_users_online Currently online users
# TYPE bot_users_online gauge
bot_users_online {active_users}

# HELP bot_downloads_total Total number of downloads
# TYPE bot_downloads_total counter
bot_downloads_total {stats['total_downloads']}

# HELP bot_downloads_today Downloads today
# TYPE bot_downloads_today gauge
bot_downloads_today {stats['today_downloads']}

# HELP bot_revenue_monthly Monthly revenue in IRR
# TYPE bot_revenue_monthly gauge
bot_revenue_monthly {stats['monthly_revenue']}

# HELP bot_queue_size Download queue size by priority
# TYPE bot_queue_size gauge
"""
            
            for queue_name, size in queue_stats.items():
                metrics_text += f'bot_queue_size{{priority="{queue_name}"}} {size}\n'
            
            # System metrics
            metrics_text += f"""
# HELP system_cpu_usage_percent CPU usage percentage
# TYPE system_cpu_usage_percent gauge
system_cpu_usage_percent {psutil.cpu_percent()}

# HELP system_memory_usage_percent Memory usage percentage
# TYPE system_memory_usage_percent gauge
system_memory_usage_percent {psutil.virtual_memory().percent}

# HELP system_disk_usage_percent Disk usage percentage
# TYPE system_disk_usage_percent gauge
system_disk_usage_percent {psutil.disk_usage('/').percent}

# HELP bot_uptime_seconds Bot uptime in seconds
# TYPE bot_uptime_seconds counter
bot_uptime_seconds {time.time() - self.start_time}
"""
            
            return web.Response(text=metrics_text, content_type='text/plain')
            
        except Exception as e:
            logger.error(f"Metrics generation failed: {str(e)}")
            return web.Response(text=f"# Error: {str(e)}", status=500)
    
    async def readiness_check(self, request):
        """بررسی آمادگی برای دریافت ترافیک"""
        try:
            # بررسی اتصالات ضروری
            await mongo_manager.db.command('ping')
            await redis_manager.client.ping()
            
            # بررسی صف‌ها
            queue_stats = await redis_manager.get_queue_stats()
            total_queue = sum(queue_stats.values())
            
            # اگر صف خیلی پر است، not ready
            if total_queue > 1000:
                return web.json_response({
                    'ready': False,
                    'reason': 'Queue overloaded',
                    'queue_size': total_queue
                }, status=503)
            
            return web.json_response({
                'ready': True,
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            return web.json_response({
                'ready': False,
                'error': str(e)
            }, status=503)
    
    async def liveness_check(self, request):
        """بررسی زنده بودن برنامه"""
        return web.json_response({
            'alive': True,
            'timestamp': datetime.now().isoformat(),
            'uptime': time.time() - self.start_time
        })
    
    async def start(self, host='0.0.0.0', port=8080):
        """شروع سرور"""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()
        logger.info(f"Health check server started on http://{host}:{port}")
    
    async def stop(self):
        """توقف سرور"""
        await self.app.shutdown()
        await self.app.cleanup()
        logger.info("Health check server stopped")

# Middleware برای لاگ
@web.middleware
async def logging_middleware(request, handler):
    """لاگ کردن درخواست‌ها"""
    start_time = time.time()
    try:
        response = await handler(request)
        duration = time.time() - start_time
        logger.info(f"{request.method} {request.path} - {response.status} ({duration:.3f}s)")
        return response
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"{request.method} {request.path} - Error: {str(e)} ({duration:.3f}s)")
        raise

# اضافه کردن به bot.py
async def setup_health_check(bot_instance):
    """راه‌اندازی health check server"""
    health_server = HealthCheckServer(bot_instance)
    health_server.app.middlewares.append(logging_middleware)
    await health_server.start(port=8443)
    return health_server