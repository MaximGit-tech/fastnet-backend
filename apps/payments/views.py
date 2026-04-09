from models import Payment
from subscriptions.models import Subscription, Plan
from vpn.panel_client import panel
from time import timezone, timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from users.models import TelegramUser
import os
import yookassa
import uuid
import json


SBP_PHONE = os.getenv("SBP_PHONE")
SBP_BANK  = os.getenv("SBP_BANK")
YOOKASSA_RETURN_URL = os.getenv("YOOKASSA_RETURN_URL")

def activate_subscription(payment: Payment):
    """
    Активирует подписку после подтверждения оплаты.
    Создаёт VPN ключи и файл подписки через panel.create_subscription().
    """
    sub = Subscription.objects.create(
        user=payment.user,
        plan=payment.plan,
        status='pending'
    )
    result = panel.create_subscription(
        telegram_id=panel.user.telegram_id,
        subscription_id=sub.id,
        days=payment.plan.days
    )

    sub.panel_uuid = result['panel_uuid']
    sub.sub_id = result["sub_id"]
    sub.status = "active"
    sub.expires_at = timezone.now() + timedelta(days=payment.plan.days)
    sub.save()

    payment.subscription = sub
    payment.status = "paid"
    payment.paid_at = timezone.now()
    payment.save()

    return sub


class SBPPaymentCreateView(APIView):
    """
    POST /api/v1/payments/yookassa/create/
    Создаёт платёж в ЮKassa и возвращает ссылку на оплату.
    Пользователь переходит по ссылке, оплачивает, ЮKassa шлёт webhook.
    """
    def post(self, request):
        telegram_id = request.data.get("telegram_id")
        plan_key    = request.data.get("plan_key")

        user = TelegramUser.objects.get(telegram_id=telegram_id)
        plan = Plan.objects.get(key=plan_key)

        payment_data = yookassa.Payment.create({
            "amount": {
                "value":    f"{plan.price_rub}.00",
                "currency": "RUB"
            },
            "confirmation": {
                "type":       "redirect",
                "return_url": YOOKASSA_RETURN_URL
            },
            "capture":     True,
            "description": f"VPN {plan.name}",
            "metadata": {
                "telegram_id": str(telegram_id),
                "plan_key":    plan_key,
            }
        }, str(uuid.uuid4()))

        payment = Payment.objects.create(
            user=user, plan=plan,
            method="manual",
            amount_rub=plan.price_rub,
            provider_payment_id=payment_data.id,
        )

        return Response({
            "payment_id":       payment.id,
            "payment_url":      payment_data.confirmation.confirmation_url,
            "yukassa_payment_id": payment_data.id,
        })
        
        
@method_decorator(csrf_exempt, name="dispatch")
class YookassaWebhookView(APIView):
    """
    POST /webhook/yookassa/
    Принимает уведомления от ЮKassa об успешной оплате.
    Верификация через IP-адреса ЮKassa или подпись.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            data   = json.loads(request.body)
            event  = data.get("event")
            obj    = data.get("object", {})
        except Exception:
            return Response(status=400)

        if event != "payment.succeeded":
            return Response(status=200)

        yookassa_payment_id = obj.get("id")
        metadata           = obj.get("metadata", {})
        telegram_id        = int(metadata.get("telegram_id", 0))
        plan_key           = metadata.get("plan_key", "")

        try:
            payment = Payment.objects.get(
                provider_payment_id=yookassa_payment_id,
                status="pending"
            )
        except Payment.DoesNotExist:
            return Response(status=200)

        sub = activate_subscription(payment)

        notify_bot(telegram_id, "subscription_activated", {
            "plan_name":  payment.plan.name,
            "sub_link":   sub.sub_link,
            "expires_at": sub.expires_at.isoformat(),
        })

        return Response(status=200)
    



