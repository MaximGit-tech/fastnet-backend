from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task
def deactivate_expired_subscriptions():
    from apps.subscriptions.models import Subscription
    from apps.utils.bot_notify import notify_bot

    expired = Subscription.objects.filter(
        status="active",
        expires_at__lte=timezone.now()
    ).select_related("user", "plan")

    count = 0
    for sub in expired:
        try:
            sub.status = "expired"
            sub.save(update_fields=["status"])
            notify_bot(sub.user, "subscription_expired", {
                "plan_name": sub.plan.name
            })
            count += 1
        except Exception as e:
            logger.error(f"Ошибка деактивации подписки {sub.id}: {e}")

    logger.info(f"Деактивировано подписок: {count}")
    return count


@shared_task
def notify_expiring_subscriptions():
    from apps.subscriptions.models import Subscription
    from apps.utils.bot_notify import notify_bot

    in_3_days = timezone.now() + timedelta(days=3)

    expiring = Subscription.objects.filter(
        status="active",
        expires_at__date=in_3_days.date()
    ).select_related("user", "plan")

    count = 0
    for sub in expiring:
        try:
            notify_bot(sub.user, "subscription_expiring", {
                "plan_name": sub.plan.name,
                "expires_at": sub.expires_at.isoformat()
            })
            count += 1
        except Exception as e:
            logger.error(f"Ошибка уведомления подписки {sub.id}: {e}")

    logger.info(f"Отправлено уведомлений об истечении: {count}")
    return count