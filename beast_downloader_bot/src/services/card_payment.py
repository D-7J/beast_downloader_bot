import random
import string
import io
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict
from PIL import Image, ImageDraw, ImageFont
import qrcode
from loguru import logger

from ..database.models import Payment, PaymentStatus
from ..config import payment_config

class CardToCardPayment:
    """سیستم پرداخت کارت به کارت"""
    
    def __init__(self):
        # لیست کارت‌های دریافت از config
        self.cards = self._load_cards()
        self.current_card_index = 0
    
    def _load_cards(self) -> list:
        """بارگذاری کارت‌ها از کانفیگ"""
        return payment_config.card_numbers
    
    def get_next_card(self) -> dict:
        """دریافت کارت بعدی (برای توزیع بار)"""
        card = self.cards[self.current_card_index]
        self.current_card_index = (self.current_card_index + 1) % len(self.cards)
        return card
    
    def generate_tracking_code(self) -> str:
        """تولید کد پیگیری یکتا"""
        date_part = datetime.now().strftime('%y%m%d')
        random_part = ''.join(random.choices(string.digits, k=6))
        return f"PAY{date_part}{random_part}"
    
    async def create_payment_info(self, payment: Payment) -> Dict:
        """ایجاد اطلاعات پرداخت"""
        card = self.get_next_card()
        tracking_code = self.generate_tracking_code()
        
        payment_info = {
            'card': card,
            'tracking_code': tracking_code,
            'amount': payment.amount,
            'expires_at': datetime.now() + timedelta(minutes=payment_config.payment_timeout_minutes),
            'created_at': datetime.now()
        }
        
        # ذخیره در metadata
        payment.metadata = {
            'method': 'card_to_card',
            'tracking_code': tracking_code,
            'card_number': card['number'],
            'card_owner': card['owner'],
            'bank': card['bank'],
            'expires_at': payment_info['expires_at'].isoformat()
        }
        
        return payment_info
    
    async def generate_payment_image(self, payment_info: Dict) -> bytes:
        """تولید تصویر اطلاعات پرداخت"""
        try:
            # ایجاد تصویر با پس‌زمینه سفید
            width, height = 600, 800
            img = Image.new('RGB', (width, height), color='white')
            draw = ImageDraw.Draw(img)
            
            # تنظیم فونت
            try:
                # مسیر فونت فارسی - می‌تونید تغییر بدید
                font_large = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 28)
                font_normal = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 20)
                font_small = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 16)
            except:
                font_large = ImageFont.load_default()
                font_normal = ImageFont.load_default()
                font_small = ImageFont.load_default()
            
            # رنگ‌ها
            primary_color = (37, 99, 235)  # آبی
            secondary_color = (75, 85, 99)  # خاکستری تیره
            success_color = (34, 197, 94)  # سبز
            danger_color = (239, 68, 68)   # قرمز
            
            # Header
            header_height = 80
            draw.rectangle([(0, 0), (width, header_height)], fill=primary_color)
            draw.text((width//2, header_height//2), "پرداخت کارت به کارت", 
                     fill='white', font=font_large, anchor="mm")
            
            # Body
            y_offset = header_height + 40
            padding_x = 40
            
            # مبلغ
            draw.text((padding_x, y_offset), "مبلغ قابل پرداخت:", 
                     fill=secondary_color, font=font_normal)
            y_offset += 35
            amount_text = f"{payment_info['amount']:,} تومان".replace(',', '،')
            draw.text((padding_x + 20, y_offset), amount_text, 
                     fill=danger_color, font=font_large)
            y_offset += 60
            
            # اطلاعات کارت
            card = payment_info['card']
            draw.text((padding_x, y_offset), "شماره کارت:", 
                     fill=secondary_color, font=font_normal)
            y_offset += 35
            
            # نمایش شماره کارت به صورت جدا
            card_number = card['number']
            draw.text((padding_x + 20, y_offset), card_number, 
                     fill='black', font=font_large)
            y_offset += 50
            
            draw.text((padding_x, y_offset), f"صاحب حساب: {card['owner']}", 
                     fill=secondary_color, font=font_normal)
            y_offset += 35
            
            draw.text((padding_x, y_offset), f"بانک: {card['bank']}", 
                     fill=secondary_color, font=font_normal)
            y_offset += 50
            
            # کد پیگیری
            draw.text((padding_x, y_offset), "کد پیگیری:", 
                     fill=secondary_color, font=font_normal)
            y_offset += 35
            draw.text((padding_x + 20, y_offset), payment_info['tracking_code'], 
                     fill=success_color, font=font_large)
            y_offset += 60
            
            # QR Code
            qr = qrcode.QRCode(version=1, box_size=8, border=2)
            qr.add_data(card['number'].replace('-', ''))
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white")
            qr_size = 180
            qr_img = qr_img.resize((qr_size, qr_size))
            
            # موقعیت QR code در وسط
            qr_x = (width - qr_size) // 2
            img.paste(qr_img, (qr_x, y_offset))
            y_offset += qr_size + 30
            
            # راهنما
            instructions = [
                "۱. مبلغ را به شماره کارت فوق واریز نمایید",
                "۲. کد پیگیری را یادداشت کنید",
                "۳. پس از واریز، دکمه تایید پرداخت را بزنید"
            ]
            
            for instruction in instructions:
                draw.text((padding_x, y_offset), instruction, 
                         fill=secondary_color, font=font_small)
                y_offset += 25
            
            # Footer
            footer_text = f"⏰ اعتبار تا: {payment_info['expires_at'].strftime('%H:%M')}"
            draw.text((width//2, height - 30), footer_text, 
                     fill=secondary_color, font=font_small, anchor="mm")
            
            # تبدیل به bytes
            img_buffer = io.BytesIO()
            img.save(img_buffer, format='PNG', quality=95)
            img_buffer.seek(0)
            
            return img_buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Error generating payment image: {str(e)}")
            return None