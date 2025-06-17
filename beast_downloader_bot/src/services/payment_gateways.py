import requests
import hashlib
import json
from abc import ABC, abstractmethod
from typing import Dict, Optional, Tuple
from datetime import datetime
import hmac
from loguru import logger

from ..config import payment_config
from ..database.models import Payment, PaymentStatus

class PaymentGateway(ABC):
    """کلاس پایه برای درگاه‌های پرداخت"""
    
    @abstractmethod
    async def create_payment(self, payment: Payment) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        ایجاد پرداخت
        Returns: (success, payment_url, error_message)
        """
        pass
    
    @abstractmethod
    async def verify_payment(self, payment: Payment, callback_data: dict) -> Tuple[bool, Optional[str], Optional[dict]]:
        """
        تایید پرداخت
        Returns: (success, reference_id, extra_data)
        """
        pass

class ZarinpalGateway(PaymentGateway):
    """درگاه پرداخت زرین‌پال"""
    
    def __init__(self):
        self.merchant_id = payment_config.zarinpal_merchant
        self.sandbox = payment_config.zarinpal_sandbox
        
        if self.sandbox:
            self.request_url = "https://sandbox.zarinpal.com/pg/rest/WebGate/PaymentRequest.json"
            self.verify_url = "https://sandbox.zarinpal.com/pg/rest/WebGate/PaymentVerification.json"
            self.gateway_url = "https://sandbox.zarinpal.com/pg/StartPay/"
        else:
            self.request_url = "https://api.zarinpal.com/pg/v4/payment/request.json"
            self.verify_url = "https://api.zarinpal.com/pg/v4/payment/verify.json"
            self.gateway_url = "https://www.zarinpal.com/pg/StartPay/"
    
    async def create_payment(self, payment: Payment) -> Tuple[bool, Optional[str], Optional[str]]:
        """ایجاد پرداخت در زرین‌پال"""
        try:
            data = {
                "merchant_id": self.merchant_id,
                "amount": payment.amount * 10,  # تبدیل به ریال
                "callback_url": f"{payment_config.callback_url}?gateway=zarinpal&payment_id={payment._id}",
                "description": payment.description or f"پرداخت اشتراک {payment.subscription_type.value}",
                "metadata": {
                    "user_id": str(payment.user_id),
                    "payment_id": str(payment._id)
                }
            }
            
            response = requests.post(self.request_url, json=data, timeout=30)
            result = response.json()
            
            if result.get('data', {}).get('code') == 100:
                authority = result['data']['authority']
                payment_url = f"{self.gateway_url}{authority}"
                return True, payment_url, None
            else:
                error = result.get('errors', {})
                return False, None, f"Zarinpal Error: {error}"
                
        except Exception as e:
            logger.error(f"Zarinpal create payment error: {str(e)}")
            return False, None, str(e)
    
    async def verify_payment(self, payment: Payment, callback_data: dict) -> Tuple[bool, Optional[str], Optional[dict]]:
        """تایید پرداخت زرین‌پال"""
        try:
            authority = callback_data.get('Authority')
            status = callback_data.get('Status')
            
            if status != 'OK':
                return False, None, {'error': 'Payment cancelled by user'}
            
            data = {
                "merchant_id": self.merchant_id,
                "amount": payment.amount * 10,
                "authority": authority
            }
            
            response = requests.post(self.verify_url, json=data, timeout=30)
            result = response.json()
            
            if result.get('data', {}).get('code') == 100:
                ref_id = str(result['data'].get('ref_id', ''))
                card_pan = result['data'].get('card_pan', '')
                
                return True, ref_id, {'card_pan': card_pan}
            else:
                return False, None, {'error': result}
                
        except Exception as e:
            logger.error(f"Zarinpal verify error: {str(e)}")
            return False, None, {'error': str(e)}

class IDPayGateway(PaymentGateway):
    """درگاه پرداخت آیدی‌پی"""
    
    def __init__(self):
        self.api_key = payment_config.idpay_api_key
        self.sandbox = payment_config.idpay_sandbox
        self.base_url = "https://api.idpay.ir/v1.1"
    
    async def create_payment(self, payment: Payment) -> Tuple[bool, Optional[str], Optional[str]]:
        """ایجاد پرداخت در آیدی‌پی"""
        try:
            headers = {
                'X-API-KEY': self.api_key,
                'X-SANDBOX': '1' if self.sandbox else '0',
                'Content-Type': 'application/json'
            }
            
            data = {
                'order_id': str(payment._id),
                'amount': payment.amount * 10,  # ریال
                'callback': f"{payment_config.callback_url}?gateway=idpay",
                'desc': payment.description or f"اشتراک {payment.subscription_type.value}",
                'name': f"User {payment.user_id}",
            }
            
            response = requests.post(
                f"{self.base_url}/payment",
                json=data,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 201:
                result = response.json()
                payment_url = result['link']
                # ذخیره id برای verify
                payment.metadata['idpay_id'] = result['id']
                return True, payment_url, None
            else:
                error = response.json()
                return False, None, f"IDPay Error: {error.get('error_message')}"
                
        except Exception as e:
            logger.error(f"IDPay create payment error: {str(e)}")
            return False, None, str(e)
    
    async def verify_payment(self, payment: Payment, callback_data: dict) -> Tuple[bool, Optional[str], Optional[dict]]:
        """تایید پرداخت آیدی‌پی"""
        try:
            headers = {
                'X-API-KEY': self.api_key,
                'X-SANDBOX': '1' if self.sandbox else '0',
                'Content-Type': 'application/json'
            }
            
            data = {
                'id': callback_data.get('id'),
                'order_id': callback_data.get('order_id')
            }
            
            response = requests.post(
                f"{self.base_url}/payment/verify",
                json=data,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result['status'] == 100:
                    return True, result['track_id'], {
                        'card_no': result.get('payment', {}).get('card_no'),
                        'hashed_card_no': result.get('payment', {}).get('hashed_card_no')
                    }
            
            return False, None, {'error': response.json()}
            
        except Exception as e:
            logger.error(f"IDPay verify error: {str(e)}")
            return False, None, {'error': str(e)}

class PayPingGateway(PaymentGateway):
    """درگاه پرداخت پی‌پینگ"""
    
    def __init__(self):
        self.token = payment_config.payping_token
        self.base_url = "https://api.payping.ir/v2"
    
    async def create_payment(self, payment: Payment) -> Tuple[bool, Optional[str], Optional[str]]:
        """ایجاد پرداخت در پی‌پینگ"""
        try:
            headers = {
                'Authorization': f'Bearer {self.token}',
                'Content-Type': 'application/json'
            }
            
            data = {
                'amount': payment.amount,  # تومان
                'returnUrl': f"{payment_config.callback_url}?gateway=payping&payment_id={payment._id}",
                'description': payment.description or f"اشتراک {payment.subscription_type.value}",
                'clientRefId': str(payment._id)
            }
            
            response = requests.post(
                f"{self.base_url}/pay",
                json=data,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                code = result['code']
                payment_url = f"https://api.payping.ir/v2/pay/gotoipg/{code}"
                return True, payment_url, None
            else:
                error = response.json()
                return False, None, f"PayPing Error: {error}"
                
        except Exception as e:
            logger.error(f"PayPing create payment error: {str(e)}")
            return False, None, str(e)
    
    async def verify_payment(self, payment: Payment, callback_data: dict) -> Tuple[bool, Optional[str], Optional[dict]]:
        """تایید پرداخت پی‌پینگ"""
        try:
            ref_id = callback_data.get('refid')
            
            headers = {
                'Authorization': f'Bearer {self.token}',
                'Content-Type': 'application/json'
            }
            
            data = {
                'refId': ref_id,
                'amount': payment.amount
            }
            
            response = requests.post(
                f"{self.base_url}/pay/verify",
                json=data,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return True, ref_id, {
                    'cardNumber': result.get('cardNumber'),
                    'cardHashPan': result.get('cardHashPan')
                }
            else:
                return False, None, {'error': response.json()}
                
        except Exception as e:
            logger.error(f"PayPing verify error: {str(e)}")
            return False, None, {'error': str(e)}

class NextPayGateway(PaymentGateway):
    """درگاه پرداخت نکست‌پی"""
    
    def __init__(self):
        self.api_key = payment_config.nextpay_api_key
        self.request_url = "https://nextpay.org/nx/gateway/token"
        self.verify_url = "https://nextpay.org/nx/gateway/verify"
        self.gateway_url = "https://nextpay.org/nx/gateway/payment/"
    
    async def create_payment(self, payment: Payment) -> Tuple[bool, Optional[str], Optional[str]]:
        """ایجاد پرداخت در نکست‌پی"""
        try:
            data = {
                'api_key': self.api_key,
                'amount': payment.amount,  # تومان
                'order_id': str(payment._id),
                'callback_uri': f"{payment_config.callback_url}?gateway=nextpay",
                'customer_phone': payment.metadata.get('phone', ''),
            }
            
            response = requests.post(self.request_url, data=data, timeout=30)
            result = response.json()
            
            if result.get('code') == -1:
                trans_id = result['trans_id']
                payment_url = f"{self.gateway_url}{trans_id}"
                return True, payment_url, None
            else:
                return False, None, f"NextPay Error: Code {result.get('code')}"
                
        except Exception as e:
            logger.error(f"NextPay create payment error: {str(e)}")
            return False, None, str(e)
    
    async def verify_payment(self, payment: Payment, callback_data: dict) -> Tuple[bool, Optional[str], Optional[dict]]:
        """تایید پرداخت نکست‌پی"""
        try:
            trans_id = callback_data.get('trans_id')
            
            data = {
                'api_key': self.api_key,
                'trans_id': trans_id,
                'amount': payment.amount
            }
            
            response = requests.post(self.verify_url, data=data, timeout=30)
            result = response.json()
            
            if result.get('code') == 0:
                return True, trans_id, {
                    'card_holder': result.get('card_holder'),
                    'Shaparak_Ref_Id': result.get('Shaparak_Ref_Id')
                }
            else:
                return False, None, {'error': f"Code: {result.get('code')}"}
                
        except Exception as e:
            logger.error(f"NextPay verify error: {str(e)}")
            return False, None, {'error': str(e)}

class CryptoGateway(PaymentGateway):
    """درگاه پرداخت کریپتو (Nowpayments)"""
    
    def __init__(self):
        self.api_key = payment_config.nowpayments_api_key
        self.base_url = "https://api.nowpayments.io/v1"
        self.ipn_secret = payment_config.nowpayments_ipn_secret
    
    async def create_payment(self, payment: Payment) -> Tuple[bool, Optional[str], Optional[str]]:
        """ایجاد پرداخت کریپتو"""
        try:
            # دریافت نرخ تبدیل
            rates_response = requests.get(
                f"{self.base_url}/estimate",
                params={
                    'amount': payment.amount / 50000,  # تبدیل تومان به دلار تقریبی
                    'currency_from': 'usd',
                    'currency_to': 'btc'
                },
                headers={'x-api-key': self.api_key}
            )
            
            if rates_response.status_code != 200:
                return False, None, "Failed to get exchange rate"
            
            estimated_amount = rates_response.json()['estimated_amount']
            
            # ایجاد پرداخت
            headers = {
                'x-api-key': self.api_key,
                'Content-Type': 'application/json'
            }
            
            data = {
                'price_amount': payment.amount / 50000,  # دلار
                'price_currency': 'usd',
                'pay_currency': 'btc',
                'ipn_callback_url': f"{payment_config.callback_url}/crypto/ipn",
                'order_id': str(payment._id),
                'order_description': payment.description or 'Subscription payment'
            }
            
            response = requests.post(
                f"{self.base_url}/payment",
                json=data,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 201:
                result = response.json()
                payment_url = result['payment_url']
                
                # ذخیره اطلاعات کریپتو
                payment.metadata['crypto_payment_id'] = result['payment_id']
                payment.metadata['pay_address'] = result['pay_address']
                payment.metadata['pay_amount'] = result['pay_amount']
                
                return True, payment_url, None
            else:
                return False, None, f"Crypto payment error: {response.text}"
                
        except Exception as e:
            logger.error(f"Crypto payment error: {str(e)}")
            return False, None, str(e)
    
    async def verify_payment(self, payment: Payment, callback_data: dict) -> Tuple[bool, Optional[str], Optional[dict]]:
        """تایید پرداخت کریپتو از طریق IPN"""
        try:
            # بررسی امضا
            if not self._verify_ipn_signature(callback_data):
                return False, None, {'error': 'Invalid IPN signature'}
            
            payment_status = callback_data.get('payment_status')
            payment_id = callback_data.get('payment_id')
            
            if payment_status == 'finished':
                return True, payment_id, {
                    'pay_currency': callback_data.get('pay_currency'),
                    'actually_paid': callback_data.get('actually_paid'),
                    'pay_address': callback_data.get('pay_address')
                }
            elif payment_status in ['expired', 'failed']:
                return False, None, {'error': f'Payment {payment_status}'}
            else:
                # Payment still processing
                return False, None, {'status': payment_status, 'pending': True}
                
        except Exception as e:
            logger.error(f"Crypto verify error: {str(e)}")
            return False, None, {'error': str(e)}
    
    def _verify_ipn_signature(self, data: dict) -> bool:
        """بررسی امضای IPN"""
        received_hmac = data.get('hmac')
        if not received_hmac:
            return False
        
        # بازسازی payload
        sorted_data = dict(sorted(data.items()))
        sorted_data.pop('hmac', None)
        payload = json.dumps(sorted_data, separators=(',', ':'))
        
        # محاسبه HMAC
        expected_hmac = hmac.new(
            self.ipn_secret.encode(),
            payload.encode(),
            hashlib.sha512
        ).hexdigest()
        
        return hmac.compare_digest(received_hmac, expected_hmac)

class PaymentGatewayFactory:
    """Factory برای ایجاد درگاه پرداخت مناسب"""
    
    _gateways = {
        'zarinpal': ZarinpalGateway,
        'idpay': IDPayGateway,
        'payping': PayPingGateway,
        'nextpay': NextPayGateway,
        'crypto': CryptoGateway
    }
    
    @classmethod
    def create(cls, gateway_name: str) -> Optional[PaymentGateway]:
        """ایجاد instance از درگاه پرداخت"""
        gateway_class = cls._gateways.get(gateway_name.lower())
        if gateway_class:
            return gateway_class()
        return None
    
    @classmethod
    def get_available_gateways(cls) -> List[str]:
        """لیست درگاه‌های موجود"""
        return list(cls._gateways.keys())