# 🚀 راهنمای نصب و راه‌اندازی بات دانلودر

## 📋 پیش‌نیازها

### نیازمندی‌های سیستم
- **OS**: Ubuntu 20.04+ / Debian 10+ / CentOS 8+
- **RAM**: حداقل 4GB (پیشنهادی 8GB)
- **CPU**: حداقل 2 Core (پیشنهادی 4 Core)
- **Storage**: حداقل 50GB فضای آزاد
- **Python**: 3.11+
- **Docker**: 20.10+ (اختیاری)
- **Docker Compose**: 2.0+ (اختیاری)

### نیازمندی‌های نرم‌افزاری
```bash
# بروزرسانی سیستم
sudo apt update && sudo apt upgrade -y

# نصب ابزارهای ضروری
sudo apt install -y python3.11 python3.11-venv python3-pip
sudo apt install -y git curl wget ffmpeg
sudo apt install -y redis mongodb
sudo apt install -y nginx certbot python3-certbot-nginx
```

## 🔧 نصب و راه‌اندازی

### 1. کلون کردن پروژه
```bash
git clone https://github.com/yourusername/persian-downloader-bot.git
cd persian-downloader-bot
```

### 2. ایجاد محیط مجازی
```bash
python3.11 -m venv venv
source venv/bin/activate
```

### 3. نصب وابستگی‌ها
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. تنظیم متغیرهای محیطی
```bash
cp .env.example .env
nano .env
```

متغیرهای ضروری:
```env
# Bot Token از @BotFather
BOT_TOKEN=your_bot_token_here

# آیدی ادمین‌ها (با کاما جدا کنید)
ADMIN_IDS=123456789,987654321

# MongoDB
MONGO_URI=mongodb://localhost:27017/
MONGO_DB_NAME=downloader_bot

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password

# Zarinpal
ZARINPAL_MERCHANT=your_merchant_id
ZARINPAL_SANDBOX=False
PAYMENT_CALLBACK_URL=https://yourdomain.com/payment/callback
```

### 5. راه‌اندازی دیتابیس‌ها

#### MongoDB
```bash
# ایجاد کاربر برای MongoDB
mongosh
> use admin
> db.createUser({
    user: "botuser",
    pwd: "strongpassword",
    roles: [{role: "readWrite", db: "downloader_bot"}]
})
```

#### Redis
```bash
# تنظیم رمز عبور Redis
sudo nano /etc/redis/redis.conf
# اضافه کنید: requirepass your_redis_password
sudo systemctl restart redis
```

### 6. اجرای بات

#### روش 1: اجرای مستقیم
```bash
python -m src.bot
```

#### روش 2: استفاده از systemd
```bash
sudo nano /etc/systemd/system/telegram-bot.service
```

محتوای فایل:
```ini
[Unit]
Description=Persian Downloader Telegram Bot
After=network.target

[Service]
Type=simple
User=botuser
WorkingDirectory=/home/botuser/persian-downloader-bot
Environment="PATH=/home/botuser/persian-downloader-bot/venv/bin"
ExecStart=/home/botuser/persian-downloader-bot/venv/bin/python -m src.bot
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

فعال‌سازی سرویس:
```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot
sudo systemctl status telegram-bot
```

#### روش 3: استفاده از Docker (پیشنهادی)
```bash
# ساخت و اجرا با Docker Compose
docker-compose up -d

# مشاهده لاگ‌ها
docker-compose logs -f bot

# توقف
docker-compose down
```

## 🔒 تنظیمات امنیتی

### 1. Firewall
```bash
# فقط پورت‌های ضروری را باز کنید
sudo ufw allow 22/tcp  # SSH
sudo ufw allow 80/tcp  # HTTP
sudo ufw allow 443/tcp # HTTPS
sudo ufw enable
```

### 2. SSL Certificate (برای Webhook)
```bash
# نصب Let's Encrypt
sudo certbot --nginx -d yourdomain.com
```

### 3. محدودیت‌های MongoDB
```javascript
// ایجاد کاربر فقط خواندنی برای بکاپ
use downloader_bot
db.createUser({
  user: "backup_user",
  pwd: "backup_password",
  roles: [{role: "read", db: "downloader_bot"}]
})
```

### 4. محافظت از فایل .env
```bash
chmod 600 .env
chown botuser:botuser .env
```

## 🌐 تنظیم Webhook (اختیاری)

### 1. تنظیم Nginx
```nginx
server {
    listen 443 ssl;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location /webhook {
        proxy_pass http://127.0.0.1:8443;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

### 2. فعال‌سازی Webhook در .env
```env
USE_WEBHOOK=True
WEBHOOK_URL=https://yourdomain.com/webhook
```

## 📊 مانیتورینگ

### 1. Celery Flower
```bash
# دسترسی به Flower
http://your-server-ip:5555
# Username: admin
# Password: (مقدار FLOWER_PASSWORD در .env)
```

### 2. لاگ‌ها
```bash
# لاگ بات
tail -f logs/bot.log

# لاگ Celery
tail -f logs/celery.log

# با Docker
docker-compose logs -f bot
docker-compose logs -f celery_worker
```

### 3. Grafana Dashboard (اختیاری)
```bash
# اجرای stack مانیتورینگ
docker-compose --profile monitoring up -d

# دسترسی به Grafana
http://your-server-ip:3000
```

## 🔄 بروزرسانی

### 1. بروزرسانی کد
```bash
git pull origin main
pip install -r requirements.txt
```

### 2. ری‌استارت سرویس‌ها
```bash
# Systemd
sudo systemctl restart telegram-bot

# Docker
docker-compose restart
```

### 3. Migration دیتابیس
```bash
# در صورت تغییر ساختار دیتابیس
python scripts/migrate_database.py
```

## 🐛 عیب‌یابی

### مشکلات رایج

#### 1. خطای اتصال به MongoDB
```bash
# بررسی وضعیت MongoDB
sudo systemctl status mongodb

# بررسی لاگ
sudo journalctl -u mongodb -n 50
```

#### 2. خطای ffmpeg
```bash
# نصب مجدد ffmpeg
sudo apt remove ffmpeg
sudo apt install ffmpeg
```

#### 3. مشکل حافظه
```bash
# بررسی مصرف حافظه
free -h

# پاکسازی کش
sync && echo 3 > /proc/sys/vm/drop_caches
```

#### 4. محدودیت Telegram
- حداکثر 30 پیام در ثانیه به کاربران مختلف
- حداکثر 1 پیام در ثانیه به یک کاربر
- حداکثر حجم فایل: 50MB (2GB برای Bot API محلی)

## 📈 بهینه‌سازی عملکرد

### 1. تنظیمات Redis
```bash
# /etc/redis/redis.conf
maxmemory 2gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
```

### 2. تنظیمات MongoDB
```javascript
// ایجاد ایندکس‌های بهینه
db.downloads.createIndex({user_id: 1, created_at: -1})
db.users.createIndex({user_id: 1}, {unique: true})
```

### 3. تنظیمات Celery
```python
# تعداد worker بر اساس CPU
celery -A src.tasks.celery_app worker --concurrency=4

# برای سرور قوی‌تر
celery -A src.tasks.celery_app worker --concurrency=8 --max-tasks-per-child=1000
```

## 🔐 بکاپ و بازیابی

### بکاپ خودکار
```bash
# اضافه کردن به crontab
crontab -e

# بکاپ روزانه ساعت 3 صبح
0 3 * * * /home/botuser/persian-downloader-bot/scripts/backup.sh
```

### بکاپ دستی
```bash
# MongoDB
mongodump --uri="mongodb://localhost:27017/downloader_bot" --out=/backup/mongo/

# فایل‌ها
tar -czf downloads_backup.tar.gz /app/data/downloads/
```

### بازیابی
```bash
# MongoDB
mongorestore --uri="mongodb://localhost:27017/downloader_bot" /backup/mongo/downloader_bot/

# فایل‌ها
tar -xzf downloads_backup.tar.gz -C /
```

## 📞 پشتیبانی

در صورت بروز مشکل:
1. بررسی لاگ‌ها
2. مطالعه [مستندات](README.md)
3. جستجو در [Issues](https://github.com/yourusername/persian-downloader-bot/issues)
4. ایجاد Issue جدید با جزئیات کامل

## 🎉 موفق باشید!

اگر همه مراحل را به درستی انجام داده‌اید، بات شما باید فعال باشد. برای تست:
```
/start
```

---
*آخرین بروزرسانی: 2024*