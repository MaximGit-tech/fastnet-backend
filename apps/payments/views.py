from .models import Payment
from apps.subscriptions.models import Subscription, Plan
from django.utils import timezone
from datetime import timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from apps.users.models import User
from apps.utils.bot_notify import notify_bot
from apps.utils.views import CsrfExemptAPIView
from yookassa import Configuration, Payment as YooPayment
import os
import uuid
import json


Configuration.account_id = os.getenv("YOOKASSA_SHOP_ID")
Configuration.secret_key = os.getenv("YOOKASSA_SECRET_KEY")

YOOKASSA_RETURN_URL = os.getenv("YOOKASSA_RETURN_URL", "https://t.me/your_bot")


def activate_subscription(payment: Payment):
    from apps.vpn.panel_client import panel
    sub = Subscription.objects.create(
        user=payment.user,
        plan=payment.plan,
        status="pending"
    )
    result = panel.create_subscription(
        user_id=payment.user.id,
        subscription_id=sub.id,
        days=payment.plan.days
    )
    sub.panel_uuid = result["panel_uuid"]
    sub.sub_id     = result["sub_id"]
    sub.status     = "active"
    sub.expires_at = timezone.now() + timedelta(days=payment.plan.days)
    sub.save()

    payment.subscription = sub
    payment.status       = "paid"
    payment.paid_at      = timezone.now()
    payment.save()

    return sub

class YookassaPaymentCreateView(CsrfExemptAPIView):
    """
    POST /api/v1/payment/yookassa/create/
    """
    def post(self, request):
        email = request.data.get("email")
        plan_key = request.data.get("plan_key")

        if not email or not plan_key:
            return Response({"error": "email и plan_key обязательны"}, status=400)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "Пользователь не найден"}, status=404)

        try:
            plan = Plan.objects.get(key=plan_key, is_active=True)
        except Plan.DoesNotExist:
            return Response({"error": f"План '{plan_key}' не найден"}, status=404)

        payment_data = YooPayment.create({
            "amount": {
                "value": f"{plan.price_rub}.00",
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": YOOKASSA_RETURN_URL
            },
            "capture": True,
            "description": f"FastNet подписка — {plan.name}",
            "metadata": {
                "email": str(email),
                "plan_key": plan_key,
            }
        }, str(uuid.uuid4()))

        payment = Payment.objects.create(
            user=user,
            plan=plan,
            method="yookassa",
            amount_rub=plan.price_rub,
            provider_charge_id=payment_data.id, 
        )

        return Response({
            "payment_id": payment.id,
            "payment_url": payment_data.confirmation.confirmation_url,
            "yookassa_payment_id": payment_data.id,
        })


class YookassaWebhookView(CsrfExemptAPIView):
    """
    POST /api/v1/payment/webhook/yookassa/
    Вебхук от ЮKassa — вызывается автоматически после оплаты.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            data = json.loads(request.body)
        except Exception:
            return Response(status=400)

        event = data.get("event")
        obj = data.get("object", {})

        if event != "payment.succeeded":
            return Response(status=200)

        yookassa_payment_id = obj.get("id")

        try:
            payment = Payment.objects.get(
            provider_charge_id=yookassa_payment_id, 
            status="pending"
        )
        except Payment.DoesNotExist:
            return Response(status=200)

        sub = activate_subscription(payment)

        notify_bot(payment.user, "subscription_activated", {
            "plan_name": payment.plan.name,
            "sub_link": sub.sub_link,
            "expires_at": sub.expires_at.isoformat(),
        })

        return Response(status=200)