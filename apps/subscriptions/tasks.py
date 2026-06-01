from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task
def deactivate_expired_subscriptions():
    from apps.subscriptions.models import Subscription
    from apps.utils.bot_notify import notify_bot
    from apps.vpn.panel_client import panel
    import os, json

    PANEL_URL = os.getenv("PANEL_URL")
    INBOUND_ID = int(os.getenv("PANEL_INBOUND_ID", "1"))

    expired = Subscription.objects.filter(
        status="active",
        expires_at__lte=timezone.now()
    ).select_related("user", "plan")

    count = 0
    for sub in expired:
        try:
            sub.status = "expired"
            sub.save(update_fields=["status"])
            if sub.panel_uuid:
                try:
                    session = panel._get_session()
                    session.post(
                        f"{PANEL_URL}/panel/api/inbounds/updateClient/{sub.panel_uuid}",
                        json={
                            "id": INBOUND_ID,
                            "settings": json.dumps({"clients": [{
                                "id": sub.panel_uuid,
                                "email": f"u{sub.user.id}_{sub.id}",
                                "enable": False,
                                "expiryTime": 0,
                                "flow": "xtls-rprx-vision",
                                "limitIp": 3,
                                "totalGB": 0,
                            }]})
                        }
                    )
                except Exception as e:
                    logger.error(f"Ошибка отключения клиента {sub.panel_uuid}: {e}")

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


@shared_task
def notify_trial_expiring():
    from apps.subscriptions.models import Subscription
    from apps.utils.bot_notify import notify_bot
    in_1_day = timezone.now() + timedelta(days=1)
    expiring = Subscription.objects.filter(
        status="active",
        plan__key="trial",
        expires_at__date=in_1_day.date()
    ).select_related("user", "plan")
    count = 0
    for sub in expiring:
        try:
            notify_bot(sub.user, "trial_expiring", {
                "expires_at": sub.expires_at.isoformat()
            })
            count += 1
        except Exception as e:
            logger.error(f"Ошибка уведомления триала {sub.id}: {e}")
    logger.info(f"Отправлено уведомлений о конце триала: {count}")
    return count