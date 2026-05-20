from .models import Payment
from apps.subscriptions.models import Subscription, Plan
from django.utils import timezone
from datetime import timedelta
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from apps.users.models import User
from apps.utils.bot_notify import notify_bot
from apps.utils.views import CsrfExemptAPIView
from yookassa import Configuration, Payment as YooPayment
import os
import uuid
import json


Configuration.account_id = os.getenv("YOOKASSA_SHOP_ID")
Configuration.secret_key = os.getenv("YOOKASSA_SECRET_KEY")

YOOKASSA_RETURN_URL = os.getenv("YOOKASSA_RETURN_URL", "https://t.me/fastnet_serv_bot")


def activate_subscription(payment: Payment):
    from apps.vpn.panel_client import panel

    if payment.subscription_id:
        sub = payment.subscription

        if sub.status == "active" and sub.expires_at:
            sub.expires_at = sub.expires_at + timedelta(days=payment.plan.days)
        else:
            sub.expires_at = timezone.now() + timedelta(days=payment.plan.days)

        panel.renew_subscription(
            telegram_id=payment.user.telegram_id,
            subscription_id=sub.id,
            panel_uuid=sub.panel_uuid,
            sub_id=sub.sub_id,
            days=payment.plan.days
        )

        sub.status = "active"
        sub.save()

        payment.status = "paid"
        payment.paid_at = timezone.now()
        payment.save()

        return sub

    else:
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
        sub.sub_id = result["sub_id"]
        sub.status = "active"
        sub.expires_at = timezone.now() + timedelta(days=payment.plan.days)
        sub.save()

        payment.subscription = sub
        payment.status = "paid"
        payment.paid_at = timezone.now()
        payment.save()

        return sub


class YookassaPaymentCreateView(CsrfExemptAPIView):
    """
    POST /api/v1/payment/yookassa/create/
    """
    def post(self, request):
        from apps.utils.authentication import get_user_from_request

        user, err = get_user_from_request(request)
        if err:
            return err

        plan_key = request.data.get("plan_key")
        subscription_id = request.data.get("subscription_id")

        if not plan_key:
            return Response({"error": "plan_key обязателен"}, status=400)

        try:
            plan = Plan.objects.get(key=plan_key, is_active=True)
        except Plan.DoesNotExist:
            return Response({"error": f"План '{plan_key}' не найден"}, status=404)

        sub = None
        if subscription_id:
            try:
                sub = Subscription.objects.get(id=subscription_id, user=user)
            except Subscription.DoesNotExist:
                return Response({"error": "Подписка не найдена"}, status=404)

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
            "description": f"FastNet {'продление' if sub else 'подписка'} — {plan.name}",
            "metadata": {
                "plan_key": plan_key,
                "subscription_id": str(subscription_id) if subscription_id else "",
            }
        }, str(uuid.uuid4()))

        payment = Payment.objects.create(
            user=user,
            plan=plan,
            subscription=sub,
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
    POST /api/v1/payment/yookassa/webhook/
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
            payment = Payment.objects.select_related(
                "user", "plan", "subscription"
            ).get(
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