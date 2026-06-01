from ..subscriptions.models import Subscription
from django.utils import timezone
from datetime import timedelta
from ..payments.models import Payment


def activate_subscription(payment: Payment):
    from apps.vpn.panel_client import panel
    from apps.subscriptions.referral import give_referrer_bonus
    import os, json

    PANEL_URL = os.getenv("PANEL_URL")
    INBOUND_ID = int(os.getenv("PANEL_INBOUND_ID", "1"))

    if payment.subscription_id:
        sub = payment.subscription
        if sub.status == "active" and sub.expires_at:
            sub.expires_at = sub.expires_at + timedelta(days=payment.plan.days)
        else:
            sub.expires_at = timezone.now() + timedelta(days=payment.plan.days)

        exp_ms = int(sub.expires_at.timestamp() * 1000)

        session = panel._get_session()
        session.post(
            f"{PANEL_URL}/panel/api/inbounds/updateClient/{sub.panel_uuid}",
            json={
                "id": INBOUND_ID,
                "settings": json.dumps({"clients": [{
                    "id": sub.panel_uuid,
                    "email": f"u{sub.user.id}_{sub.id}",
                    "enable": True,
                    "expiryTime": exp_ms,
                    "flow": "xtls-rprx-vision",
                    "limitIp": 3,
                    "totalGB": 0,
                }]})
            }
        )

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

    user = payment.user
    if (
        user.referred_by
        and not user.referred_by.referral_bonus_given
    ):
        give_referrer_bonus(
            referrer=user.referred_by,
            friend=user,
        )

    return sub