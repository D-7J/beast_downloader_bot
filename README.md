# Beast Downloader Bot

ربات دانلودر حرفه‌ای تلگرام با قابلیت مدیریت اشتراک و پرداخت کارت به کارت

## ویژگی‌ها

- دانلود از منابع مختلف
- سیستم اشتراک‌گذاری
- پنل مدیریت کاربران

## 🛠️ پیش‌نیازها

- پایتون ۳.۹ یا بالاتر
- PostgreSQL (برای دیتابیس)
- Redis (برای کش و محدودیت نرخ)
- FFmpeg (برای پردازش ویدیو)
- توکن ربات تلگرام از [@BotFather](https://t.me/BotFather)

## 🚀 راه‌اندازی

1. مخزن را کلون کنید:
   ```bash
   git clone https://github.com/yourusername/beast_downloader_bot.git
   cd beast_downloader_bot
   ```

2. محیط مجازی بسازید و فعال کنید:
   ```bash
   # ویندوز
   python -m venv venv
   .\venv\Scripts\activate
   
   # لینوکس/مک
   python3 -m venv venv
   source venv/bin/activate
   ```

3. وابستگی‌ها را نصب کنید:
   ```bash
   pip install -r requirements.txt
   ```

4. فایل تنظیمات را کپی و تنظیم کنید:
   ```bash
   copy .env.example .env
   ```
   سپس فایل `.env` را با اطلاعات خود پر کنید.

5. دیتابیس را راه‌اندازی کنید:
   ```bash
   python -m database.init_db
   ```

## پلن‌های اشتراک

- 🆓 رایگان (5 دانلود روزانه - حداکثر 50 مگابایت)
- 🥉 برنزی (50,000 تومان/ماه)
- 🥈 نقره‌ای (100,000 تومان/ماه)
- 🥇 طلایی (200,000 تومان/ماه)

## راه‌های ارتباطی

- [کانال تلگرام](https://t.me/yourchannel)
- [پشتیبانی](https://t.me/yoursupport)

## لایسنس

این پروژه تحت مجوز MIT منتشر شده است.
