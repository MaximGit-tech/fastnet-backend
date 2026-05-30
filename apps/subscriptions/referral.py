import logging
from datetime import timedelta
from typing import Optional

from django.utils import timezone

from apps.subscriptions.models import Subscription, Plan
from apps.vpn.panel_client import panel
from apps.utils.bot_notify import notify_bot

logger = logging.getLogger(__name__)

REFERRER_BONUS_DAYS = 30
FRIEND_BONUS_DAYS   = 7 

def _get_or_create_plan(key: str, name: str, days: int) -> Optional[object]:
    try:
        from apps.subscriptions.models import Plan
        return Plan.objects.get(key=key, is_active=True)
    except Plan.DoesNotExist:
        logger.error(f"Plan '{key}' not found. Create it in DB.")
        return None


def _create_subscription(user, plan, days: int) -> Optional[Subscription]:
    sub = Subscription.objects.create(
        user=user,
        plan=plan,
        status="pending",
    )
    try:
        result = panel.create_subscription(
            user_id=user.id,
            subscription_id=sub.id,
            days=days,
        )
    except Exception as e:
        logger.error(f"Panel error for user {user.id}: {e}")
        sub.delete()
        return None

    sub.panel_uuid = result["panel_uuid"]
    sub.sub_id     = result["sub_id"]
    sub.status     = "active"
    sub.expires_at = timezone.now() + timedelta(days=days)
    sub.save()
    return sub


def _extend_subscription(sub: Subscription, days: int) -> Subscription:
    try:
        panel.renew_subscription(
            subscription_id=sub.id,
            days=days,
        )
    except Exception as e:
        logger.error(f"Panel renew error for sub {sub.id}: {e}")
        raise

    if sub.expires_at and sub.expires_at > timezone.now():
        sub.expires_at += timedelta(days=days)
    else:
        sub.expires_at = timezone.now() + timedelta(days=days)

    sub.status = "active"
    sub.save(update_fields=["expires_at", "status"])
    return sub


def give_friend_bonus(friend) -> Optional[Subscription]:
    plan = _get_or_create_plan("referral_friend", "Реферальный бонус (друг)", FRIEND_BONUS_DAYS)
    if not plan:
        plan = Plan.objects.filter(is_active=True, price_rub__gt=0).first()
    if not plan:
        return None

    sub = _create_subscription(friend, plan, FRIEND_BONUS_DAYS)
    if sub:
        friend.has_used_trial = True
        friend.save(update_fields=["has_used_trial"])

    return sub


def give_referrer_bonus(referrer, friend) -> Optional[Subscription]:
    if referrer.referral_bonus_given:
        logger.info(f"Referrer {referrer.id} already received bonus, skipping.")
        return None

    plan = _get_or_create_plan("referral_referrer", "Реферальный бонус (реферер)", REFERRER_BONUS_DAYS)
    if not plan:
        plan = Plan.objects.filter(is_active=True, price_rub__gt=0).first()
    if not plan:
        return None

    best_sub = (
        Subscription.objects
        .filter(user=referrer, status="active")
        .order_by("-expires_at")
        .first()
    )

    if best_sub:
        try:
            sub = _extend_subscription(best_sub, REFERRER_BONUS_DAYS)
            action = "extended"
        except Exception:
            return None
    else:
        sub = _create_subscription(referrer, plan, REFERRER_BONUS_DAYS)
        action = "created"

    if sub:
        referrer.referral_bonus_given = True
        referrer.save(update_fields=["referral_bonus_given"])

        friend_name = friend.full_name or friend.username or friend.email
        notify_bot(referrer, "referral_bonus", {
            "friend_name": friend_name,
            "action":      action, 
            "sub_link":    sub.sub_link,
            "expires_at":  sub.expires_at.isoformat(),
        })

    return sub