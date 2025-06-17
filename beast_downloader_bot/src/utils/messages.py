"""
پیام‌های بات به زبان فارسی
"""

# پیام‌های خوش‌آمدگویی
WELCOME_MESSAGE = """
سلام {first_name} عزیز! 👋

به قدرتمندترین ربات دانلود از شبکه‌های اجتماعی خوش آمدید! 

✅ **امکانات ربات:**
• دانلود از یوتیوب، اینستاگرام، توییتر، تیک‌تاک و +50 سایت دیگر
• دانلود با بهترین کیفیت (تا 4K)
• تبدیل ویدیو به MP3
• دانلود پلی‌لیست (کاربران VIP)
• دانلود زیرنویس
• بدون محدودیت زمانی برای کاربران طلایی

🔗 **نحوه استفاده:**
فقط لینک ویدیو را ارسال کنید!

💎 اشتراک فعلی شما: **{subscription}**
📥 دانلود امروز: **{downloads_today}/{daily_limit}**
"""

HELP_MESSAGE = """
📚 **راهنمای کامل استفاده:**

**🔗 نحوه دانلود:**
1️⃣ لینک ویدیو را کپی کنید
2️⃣ لینک را برای ربات ارسال کنید
3️⃣ کیفیت دلخواه را انتخاب کنید
4️⃣ صبر کنید تا فایل دانلود شود

**✅ سایت‌های پشتیبانی شده:**
• YouTube (ویدیو، شورت، پلی‌لیست)
• Instagram (پست، ریلز، استوری، IGTV)
• Twitter/X (توییت، GIF)
• TikTok (بدون واترمارک)
• Facebook
• Reddit
• Pinterest
• و بیش از 50 سایت دیگر...

**💡 نکات مهم:**
• برای دانلود از اینستاگرام، پیج باید عمومی باشد
• برای دانلود استوری، باید لینک مستقیم استوری را ارسال کنید
• حداکثر حجم برای کاربران رایگان: 50 مگابایت
• دانلود پلی‌لیست فقط برای کاربران طلایی

**⚡ دستورات ربات:**
/start - شروع مجدد
/help - راهنما
/profile - پروفایل من
/subscription - خرید اشتراک
/support - پشتیبانی

🆘 **پشتیبانی:** @YourSupportBot
📢 **کانال:** @YourChannelUsername
"""

# پیام‌های اشتراک
SUBSCRIPTION_PLANS = """
💎 **پلن‌های اشتراک ویژه:**

🆓 **رایگان**
├ 5 دانلود روزانه
├ حداکثر 50 مگابایت
├ کیفیت 720p
└ با واترمارک

🥉 **برنزی - 50,000 تومان/ماه**
├ 50 دانلود روزانه
├ حداکثر 200 مگابایت
├ کیفیت 1080p
├ بدون واترمارک
└ اولویت در صف

🥈 **نقره‌ای - 100,000 تومان/ماه**
├ 150 دانلود روزانه
├ حداکثر 500 مگابایت
├ کیفیت 1080p+
├ دانلود زیرنویس
├ انتخاب فرمت دلخواه
└ دانلود سریع‌تر

🥇 **طلایی - 200,000 تومان/ماه**
├ دانلود نامحدود
├ حداکثر 2 گیگابایت
├ کیفیت 4K
├ دانلود پلی‌لیست
├ دانلود همزمان 5 فایل
├ بدون محدودیت زمان ویدیو
└ پشتیبانی اختصاصی 24/7

🎁 **با خرید اشتراک 10% تخفیف برای دوستانتان دریافت کنید!**

برای خرید روی پلن مورد نظر کلیک کنید 👇
"""

# پیام‌های وضعیت
PROCESSING_VIDEO_INFO = "🔄 در حال دریافت اطلاعات ویدیو..."
DOWNLOADING_VIDEO = "⏳ در حال دانلود ویدیو...\n\n{progress}"
DOWNLOAD_COMPLETED = "✅ دانلود با موفقیت انجام شد!"
UPLOADING_FILE = "📤 در حال آپلود فایل..."

# پیام‌های خطا
ERROR_INVALID_URL = """
❌ **لینک نامعتبر!**

لطفاً یک لینک معتبر از سایت‌های پشتیبانی شده ارسال کنید.

مثال:
• `https://youtube.com/watch?v=...`
• `https://instagram.com/p/...`
• `https://twitter.com/.../status/...`
"""

ERROR_PRIVATE_CONTENT = """
❌ **محتوا خصوصی است!**

این ویدیو/پست خصوصی است و قابل دانلود نیست.
لطفاً از محتوای عمومی استفاده کنید.
"""

ERROR_DOWNLOAD_FAILED = """
❌ **خطا در دانلود!**

متأسفانه دانلود با خطا مواجه شد.
لطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید.

کد خطا: `{error_code}`
"""

ERROR_FILE_TOO_LARGE = """
❌ **فایل بسیار بزرگ است!**

حجم فایل: **{file_size}**
حداکثر مجاز: **{max_size}**

💎 برای دانلود فایل‌های بزرگتر، اشتراک خود را ارتقا دهید.
"""

ERROR_DURATION_LIMIT = """
❌ **ویدیو بسیار طولانی است!**

مدت ویدیو: **{duration}**
حداکثر مجاز: **{max_duration}**

💎 کاربران طلایی محدودیت زمانی ندارند!
"""

ERROR_DAILY_LIMIT = """
⚠️ **محدودیت روزانه!**

شما به محدودیت روزانه خود رسیده‌اید.

📊 **آمار امروز شما:**
• تعداد دانلود: {downloads_today}/{daily_limit}
• حجم دانلود: {size_today}

⏰ محدودیت در {reset_time} دیگر ریست می‌شود.

💎 **برای دانلود بیشتر، اشتراک خود را ارتقا دهید!**
"""

ERROR_CONCURRENT_LIMIT = """
⚠️ **دانلود همزمان!**

شما {current_concurrent} دانلود همزمان فعال دارید.
حداکثر مجاز: {concurrent_limit}

لطفاً صبر کنید تا دانلود‌های فعلی تمام شوند.

💎 کاربران طلایی می‌توانند تا 5 فایل را همزمان دانلود کنند!
"""

ERROR_NOT_SUPPORTED = """
❌ **سایت پشتیبانی نمی‌شود!**

متأسفانه این سایت/پلتفرم هنوز پشتیبانی نمی‌شود.

لیست سایت‌های پشتیبانی شده را با دستور /help مشاهده کنید.
"""

ERROR_MAINTENANCE = """
🛠 **ربات در حال تعمیر است!**

در حال حاضر ربات در دست تعمیر می‌باشد.
لطفاً کمی بعد دوباره تلاش کنید.

زمان تقریبی: {estimated_time}
"""

# پیام‌های پروفایل
USER_PROFILE = """
👤 **پروفایل شما**

🆔 شناسه: `{user_id}`
📅 تاریخ عضویت: {joined_date}
💎 نوع اشتراک: **{subscription}**
⏰ انقضای اشتراک: {subscription_expires}

📊 **آمار کلی:**
├ کل دانلودها: **{total_downloads}**
├ حجم کل: **{total_size}**
├ امتیاز معرفی: **{referral_score}**
└ تعداد دعوت: **{referral_count}**

📈 **آمار امروز:**
├ تعداد دانلود: **{downloads_today}/{daily_limit}**
├ حجم دانلود: **{size_today}**
└ دانلود همزمان: **{concurrent_downloads}/{concurrent_limit}**

🎁 لینک دعوت شما:
`https://t.me/{bot_username}?start={user_id}`
"""

# پیام‌های دانلود
VIDEO_INFO = """
📹 **{title}**

⏱ مدت زمان: {duration}
📅 تاریخ انتشار: {upload_date}
👁 بازدید: {view_count}
👤 منتشرکننده: {uploader}
🌐 پلتفرم: {platform}

🔽 **کیفیت دلخواه را انتخاب کنید:**
"""

DOWNLOAD_PROGRESS = """
📥 **در حال دانلود...**

📊 پیشرفت: {progress}%
{progress_bar}

📦 دانلود شده: {downloaded}/{total_size}
⚡ سرعت: {speed}
⏱ زمان باقی‌مانده: {eta}

لطفاً صبور باشید...
"""

DOWNLOAD_IN_QUEUE = """
⏳ **در صف دانلود**

📍 موقعیت شما در صف: **{position}**
⏱ زمان تقریبی انتظار: **{wait_time}**

💎 کاربران VIP در اولویت قرار دارند!
"""

# پیام‌های پرداخت
PAYMENT_INVOICE = """
💳 **فاکتور خرید اشتراک**

📦 پلن انتخابی: **{plan_name}**
💰 مبلغ قابل پرداخت: **{amount:,} تومان**
📅 مدت اعتبار: **30 روز**

✅ **مزایای این پلن:**
{features}

برای پرداخت روی دکمه زیر کلیک کنید 👇
"""

PAYMENT_SUCCESS = """
✅ **پرداخت موفق!**

اشتراک {plan_name} شما با موفقیت فعال شد.

📅 اعتبار تا: {expires_date}
🎁 کد تخفیف برای دوستان: `{referral_code}`

از خرید شما متشکریم! 🙏
"""

PAYMENT_FAILED = """
❌ **پرداخت ناموفق!**

متأسفانه پرداخت شما با خطا مواجه شد.
لطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید.

کد پیگیری: `{payment_id}`
"""

# پیام‌های ادمین
ADMIN_STATS = """
📊 **آمار کلی ربات**

👥 **کاربران:**
├ کل کاربران: {total_users:,}
├ کاربران فعال (7 روز): {active_users:,}
├ کاربران آنلاین: {online_users:,}
└ ثبت‌نام امروز: {new_users_today:,}

💎 **اشتراک‌ها:**
├ رایگان: {free_users:,}
├ برنزی: {bronze_users:,}
├ نقره‌ای: {silver_users:,}
└ طلایی: {gold_users:,}

📥 **دانلودها:**
├ کل دانلودها: {total_downloads:,}
├ دانلود امروز: {downloads_today:,}
├ موفق امروز: {successful_today:,}
└ ناموفق امروز: {failed_today:,}

💰 **مالی:**
├ درآمد امروز: {revenue_today:,} تومان
├ درآمد این ماه: {revenue_month:,} تومان
└ کل درآمد: {total_revenue:,} تومان

📈 **صف‌ها:**
├ صف طلایی: {gold_queue}
├ صف نقره‌ای: {silver_queue}
├ صف برنزی: {bronze_queue}
└ صف رایگان: {free_queue}

🕐 آخرین بروزرسانی: {last_update}
"""

BROADCAST_CONFIRM = """
📢 **ارسال پیام همگانی**

پیام شما:
```
{message}
```

این پیام به **{user_count:,}** کاربر ارسال خواهد شد.

آیا مطمئن هستید؟
"""

# دکمه‌ها
BUTTON_DOWNLOAD_VIDEO = "🎥 دانلود ویدیو"
BUTTON_DOWNLOAD_AUDIO = "🎵 دانلود MP3"
BUTTON_SELECT_QUALITY = "🎯 انتخاب کیفیت"
BUTTON_MY_DOWNLOADS = "📥 دانلودهای من"
BUTTON_BUY_SUBSCRIPTION = "💎 خرید اشتراک"
BUTTON_MY_PROFILE = "👤 پروفایل من"
BUTTON_HELP = "📚 راهنما"
BUTTON_SUPPORT = "🆘 پشتیبانی"
BUTTON_SHARE_BOT = "🔗 معرفی به دوستان"
BUTTON_CANCEL = "❌ لغو"
BUTTON_BACK = "🔙 بازگشت"
BUTTON_PAY = "💳 پرداخت"
BUTTON_CHECK_PAYMENT = "✅ بررسی پرداخت"

# Progress bar
def create_progress_bar(percentage: int, length: int = 10) -> str:
    """ایجاد نوار پیشرفت"""
    filled = int(length * percentage / 100)
    bar = '█' * filled + '░' * (length - filled)
    return f"[{bar}]"

# Format helpers
def format_file_size(size_bytes: int) -> str:
    """فرمت حجم فایل"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"

def format_duration(seconds: int) -> str:
    """فرمت مدت زمان"""
    if seconds < 60:
        return f"{seconds} ثانیه"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}:{secs:02d}"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours}:{minutes:02d}:{secs:02d}"

def format_number(number: int) -> str:
    """فرمت عدد با جداکننده"""
    return f"{number:,}".replace(",", "،")