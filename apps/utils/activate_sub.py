from ..subscriptions.models import Subscription
from django.utils import timezone
from datetime import timedelta
from ..payments.models import Payment


def activate_subscription(payment: Payment):
    from apps.vpn.panel_client import panel
    from apps.subscriptions.referral import give_referrer_bonus

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
        sub.sub_id     = result["sub_id"]
        sub.status     = "active"
        sub.expires_at = timezone.now() + timedelta(days=payment.plan.days)
        sub.save()
        payment.subscription = sub
        payment.status  = "paid"
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