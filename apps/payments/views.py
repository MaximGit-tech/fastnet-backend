from models import Payment
from subscriptions.models import Subscription
from vpn.panel_client import panel
from time import timezone, timedelta



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
