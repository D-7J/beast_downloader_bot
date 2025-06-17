from typing import List, Dict, Optional, Tuple
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from ..config import subscription_config
from ..database.models import SubscriptionType
from . import messages

class Keyboards:
    """مدیریت کیبوردهای بات"""
    
    @staticmethod
    def main_menu() -> InlineKeyboardMarkup:
        """منوی اصلی"""
        keyboard = [
            [
                InlineKeyboardButton(messages.BUTTON_MY_DOWNLOADS, callback_data='my_downloads'),
                InlineKeyboardButton(messages.BUTTON_MY_PROFILE, callback_data='profile')
            ],
            [
                InlineKeyboardButton(messages.BUTTON_BUY_SUBSCRIPTION, callback_data='subscription'),
                InlineKeyboardButton(messages.BUTTON_HELP, callback_data='help')
            ],
            [
                InlineKeyboardButton(messages.BUTTON_SHARE_BOT, switch_inline_query=''),
                InlineKeyboardButton(messages.BUTTON_SUPPORT, url='https://t.me/YourSupportBot')
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def video_quality_buttons(formats: List[Dict], url: str) -> InlineKeyboardMarkup:
        """دکمه‌های انتخاب کیفیت ویدیو"""
        keyboard = []
        
        # گروه‌بندی فرمت‌ها بر اساس کیفیت
        quality_groups = {}
        for fmt in formats:
            height = fmt.get('height', 0)
            if height >= 2160:
                quality = '4K'
            elif height >= 1440:
                quality = '2K'
            elif height >= 1080:
                quality = '1080p'
            elif height >= 720:
                quality = '720p'
            elif height >= 480:
                quality = '480p'
            elif height >= 360:
                quality = '360p'
            else:
                quality = '240p'
            
            if quality not in quality_groups or fmt.get('filesize', 0) > quality_groups[quality].get('filesize', 0):
                quality_groups[quality] = fmt
        
        # ایجاد دکمه‌ها
        video_buttons = []
        for quality in ['4K', '2K', '1080p', '720p', '480p', '360p', '240p']:
            if quality in quality_groups:
                fmt = quality_groups[quality]
                format_id = fmt.get('format_id')
                size = fmt.get('filesize', 0)
                
                if size > 0:
                    size_str = messages.format_file_size(size)
                    button_text = f"🎥 {quality} ({size_str})"
                else:
                    button_text = f"🎥 {quality}"
                
                # محدود کردن طول callback_data
                callback_data = f"dl_v_{format_id}_{hash(url) % 1000000}"
                video_buttons.append(
                    InlineKeyboardButton(button_text, callback_data=callback_data)
                )
        
        # چیدمان دکمه‌ها (2 تا در هر ردیف)
        for i in range(0, len(video_buttons), 2):
            row = video_buttons[i:i+2]
            keyboard.append(row)
        
        # دکمه دانلود صوت
        keyboard.append([
            InlineKeyboardButton("🎵 دانلود MP3", callback_data=f"dl_a_{hash(url) % 1000000}")
        ])
        
        # دکمه لغو
        keyboard.append([
            InlineKeyboardButton(messages.BUTTON_CANCEL, callback_data='cancel_download')
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def subscription_plans() -> InlineKeyboardMarkup:
        """دکمه‌های پلن‌های اشتراک"""
        keyboard = []
        
        for plan_key, plan in subscription_config.plans.items():
            if plan_key != 'free':
                price_str = f"{plan['price']:,} تومان".replace(',', '،')
                button_text = f"{plan['name']} - {price_str}"
                keyboard.append([
                    InlineKeyboardButton(
                        button_text,
                        callback_data=f"buy_plan_{plan_key}"
                    )
                ])
        
        keyboard.append([
            InlineKeyboardButton(messages.BUTTON_BACK, callback_data='main_menu')
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def payment_buttons(payment_url: str, payment_id: str) -> InlineKeyboardMarkup:
        """دکمه‌های پرداخت"""
        keyboard = [
            [InlineKeyboardButton(messages.BUTTON_PAY, url=payment_url)],
            [InlineKeyboardButton(messages.BUTTON_CHECK_PAYMENT, 
                                callback_data=f"check_payment_{payment_id}")],
            [InlineKeyboardButton(messages.BUTTON_CANCEL, 
                                callback_data=f"cancel_payment_{payment_id}")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def download_actions(download_id: str) -> InlineKeyboardMarkup:
        """دکمه‌های عملیات دانلود"""
        keyboard = [
            [
                InlineKeyboardButton("⏸ توقف", callback_data=f"pause_dl_{download_id}"),
                InlineKeyboardButton("❌ لغو", callback_data=f"cancel_dl_{download_id}")
            ],
            [
                InlineKeyboardButton("📊 وضعیت", callback_data=f"status_dl_{download_id}")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def user_downloads_pagination(downloads: List, page: int = 1, per_page: int = 5) -> InlineKeyboardMarkup:
        """صفحه‌بندی لیست دانلودها"""
        total_pages = (len(downloads) + per_page - 1) // per_page
        start_idx = (page - 1) * per_page
        end_idx = min(start_idx + per_page, len(downloads))
        
        keyboard = []
        
        # دکمه‌های دانلودها
        for i in range(start_idx, end_idx):
            dl = downloads[i]
            status_emoji = {
                'pending': '⏳',
                'processing': '📥',
                'completed': '✅',
                'failed': '❌',
                'cancelled': '🚫'
            }.get(dl.status.value, '❓')
            
            button_text = f"{status_emoji} {dl.title[:30]}... ({dl.created_at.strftime('%m/%d')})"
            keyboard.append([
                InlineKeyboardButton(
                    button_text,
                    callback_data=f"view_dl_{str(dl._id)[:10]}"
                )
            ])
        
        # دکمه‌های صفحه‌بندی
        nav_buttons = []
        if page > 1:
            nav_buttons.append(
                InlineKeyboardButton("◀️ قبلی", callback_data=f"dl_page_{page-1}")
            )
        
        nav_buttons.append(
            InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data="noop")
        )
        
        if page < total_pages:
            nav_buttons.append(
                InlineKeyboardButton("بعدی ▶️", callback_data=f"dl_page_{page+1}")
            )
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        keyboard.append([
            InlineKeyboardButton(messages.BUTTON_BACK, callback_data='main_menu')
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def admin_panel() -> InlineKeyboardMarkup:
        """پنل ادمین"""
        keyboard = [
            [
                InlineKeyboardButton("📊 آمار کلی", callback_data='admin_stats'),
                InlineKeyboardButton("📈 نمودارها", callback_data='admin_charts')
            ],
            [
                InlineKeyboardButton("👥 مدیریت کاربران", callback_data='admin_users'),
                InlineKeyboardButton("📢 پیام همگانی", callback_data='admin_broadcast')
            ],
            [
                InlineKeyboardButton("💰 گزارش مالی", callback_data='admin_finance'),
                InlineKeyboardButton("⚙️ تنظیمات", callback_data='admin_settings')
            ],
            [
                InlineKeyboardButton("🔄 ری‌استارت", callback_data='admin_restart'),
                InlineKeyboardButton("📥 بکاپ", callback_data='admin_backup')
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def confirm_action(action: str, data: str) -> InlineKeyboardMarkup:
        """تأیید عملیات"""
        keyboard = [
            [
                InlineKeyboardButton("✅ بله", callback_data=f"confirm_{action}_{data}"),
                InlineKeyboardButton("❌ خیر", callback_data='cancel_action')
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def share_bot(bot_username: str, user_id: int) -> InlineKeyboardMarkup:
        """دکمه اشتراک‌گذاری ربات"""
        share_text = (
            "🤖 با این ربات فوق‌العاده می‌تونی از یوتیوب، اینستاگرام و +50 سایت دیگه "
            "ویدیو دانلود کنی!\n\n"
            "💎 با ثبت‌نام از لینک من، هر دو تخفیف ویژه می‌گیریم!"
        )
        share_url = f"https://t.me/{bot_username}?start={user_id}"
        
        keyboard = [
            [InlineKeyboardButton(
                "📤 اشتراک در تلگرام",
                url=f"https://t.me/share/url?url={share_url}&text={share_text}"
            )],
            [InlineKeyboardButton(
                "📋 کپی لینک دعوت",
                callback_data='copy_referral_link'
            )]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def platform_selector() -> InlineKeyboardMarkup:
        """انتخاب پلتفرم برای آمار"""
        platforms = [
            ('YouTube', 'youtube'),
            ('Instagram', 'instagram'),
            ('Twitter', 'twitter'),
            ('TikTok', 'tiktok'),
            ('Facebook', 'facebook'),
            ('همه', 'all')
        ]
        
        keyboard = []
        for i in range(0, len(platforms), 2):
            row = []
            for name, code in platforms[i:i+2]:
                row.append(InlineKeyboardButton(name, callback_data=f"platform_{code}"))
            keyboard.append(row)
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def back_button(callback_data: str = 'main_menu') -> InlineKeyboardMarkup:
        """دکمه بازگشت"""
        return InlineKeyboardMarkup([[
            InlineKeyboardButton(messages.BUTTON_BACK, callback_data=callback_data)
        ]])
    
    @staticmethod
    def remove_keyboard() -> InlineKeyboardMarkup:
        """حذف کیبورد"""
        return InlineKeyboardMarkup([])

# Reply Keyboards (برای دستورات سریع)
class ReplyKeyboards:
    """کیبوردهای Reply"""
    
    @staticmethod
    def main_menu() -> ReplyKeyboardMarkup:
        """منوی اصلی Reply"""
        keyboard = [
            [KeyboardButton("📥 دانلودهای من"), KeyboardButton("👤 پروفایل")],
            [KeyboardButton("💎 خرید اشتراک"), KeyboardButton("📚 راهنما")],
            [KeyboardButton("🔗 دعوت دوستان")]
        ]
        return ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=False
        )
    
    @staticmethod
    def request_contact() -> ReplyKeyboardMarkup:
        """درخواست شماره تماس"""
        keyboard = [[
            KeyboardButton(
                "📱 ارسال شماره تماس",
                request_contact=True
            )
        ]]
        return ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=True
        )