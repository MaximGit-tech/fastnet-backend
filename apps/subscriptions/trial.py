from django.utils import timezone
from datetime import timedelta
from apps.subscriptions.models import Subscription, Plan
from apps.vpn.panel_client import panel
import logging

logger = logging.getLogger(__name__)

TRIAL_DAYS = 3
TRIAL_PLAN_KEY = "trial"


def activate_trial(user) -> Subscription | None:
    if user.has_used_trial:
        return None

    try:
        plan = Plan.objects.get(key=TRIAL_PLAN_KEY, is_active=True)
    except Plan.DoesNotExist:
        logger.error("Trial plan not found. Create a Plan with key='trial'.")
        return None

    sub = Subscription.objects.create(
        user=user,
        plan=plan,
        status="pending",
    )

    try:
        result = panel.create_subscription(
            user_id=user.id,
            subscription_id=sub.id,
            days=TRIAL_DAYS,
        )
    except Exception as e:
        logger.error(f"Trial panel error for user {user.id}: {e}")
        sub.delete()
        return None

    sub.panel_uuid = result["panel_uuid"]
    sub.sub_id     = result["sub_id"]
    sub.status     = "active"
    sub.expires_at = timezone.now() + timedelta(days=TRIAL_DAYS)
    sub.save()

    user.has_used_trial = True
    user.save(update_fields=["has_used_trial"])

    return sub