from apps.utils.views import CsrfExemptAPIView
from rest_framework.response import Response
from .models import Subscription, Plan
from django.utils import timezone


class UserSubscriptionListView(CsrfExemptAPIView):
    """
    GET /api/v1/subscriptions/
    """
    def get(self, request):
        from apps.utils.authentication import get_user_from_request

        user, err = get_user_from_request(request)
        if err:
            return err

        if user.is_banned:
            return Response({'error': 'user is banned'}, status=403)

        sub = Subscription.objects.filter(
            user=user,
            status='active'
        ).select_related('plan').order_by('-created_at')

        return Response([{
            "id": s.id,
            "plan_key": s.plan.key,
            "plan_name": s.plan.name,
            "status": s.status,
            "expires_at": s.expires_at.isoformat() if s.expires_at else None,
            "sub_link": s.sub_link,
            "created_at": s.created_at.isoformat(),
        } for s in sub])
            


class GetPlans(CsrfExemptAPIView):
    """GET /api/v1/subscriptions/plans/"""
    def get(self, request):
        plans = Plan.objects.filter(is_active=True, price_rub__gt=0).order_by('price_rub')

        return Response([{
            'plan_key': p.key,
            'plan_name': p.name,
            'days': p.days,
            'price_rub': p.price_rub
        } for p in plans])
    

class RenewSubscriptionView(CsrfExemptAPIView):
    """
    POST /api/v1/subscriptions/{subscription_id}/renew/
    """
    def post(self, request, subscription_id):
        from apps.vpn.panel_client import panel
        from apps.utils.authentication import get_user_from_request
        from datetime import timedelta

        user, err = get_user_from_request(request)
        if err:
            return err

        days = request.data.get("days")
        if not days:
            return Response({"error": "days обязателен"}, status=400)

        try:
            sub = Subscription.objects.get(id=subscription_id, user=user)
        except Subscription.DoesNotExist:
            return Response({"error": "Подписка не найдена"}, status=404)

        if not sub.panel_uuid or not sub.sub_id:
            return Response({"error": "Подписка не активирована"}, status=400)

        panel.renew_subscription(
            telegram_id=user.telegram_id,
            subscription_id=sub.id,
            panel_uuid=sub.panel_uuid,
            sub_id=sub.sub_id,
            days=days
        )

        if sub.status == "active" and sub.expires_at:
            sub.expires_at = sub.expires_at + timedelta(days=days)
        else:
            sub.expires_at = timezone.now() + timedelta(days=days)

        sub.status = "active"
        sub.save()

        return Response({
            "success": True,
            "subscription_id": sub.id,
            "expires_at": sub.expires_at.isoformat(),
            "sub_link": sub.sub_link,
        })


class RegenerateSubIdView(CsrfExemptAPIView):
    """
    POST /api/v1/subscriptions/{subscription_id}/regenerate/
    """
    def post(self, request, subscription_id):
        from apps.vpn.panel_client import panel
        from apps.utils.authentication import get_user_from_request
        import uuid

        user, err = get_user_from_request(request)
        if err:
            return err

        try:
            sub = Subscription.objects.get(id=subscription_id, user=user)
        except Subscription.DoesNotExist:
            return Response({"error": "Подписка не найдена"}, status=404)

        if not sub.panel_uuid or not sub.sub_id:
            return Response({"error": "Подписка не активирована"}, status=400)

        try:
            panel._delete_sub_file(sub.sub_id)
        except Exception:
            pass

        new_sub_id = uuid.uuid4().hex[:16]
        content = panel._build_subscription_content(sub.panel_uuid)
        panel._write_sub_file(new_sub_id, content)

        sub.sub_id = new_sub_id
        sub.save()

        return Response({
            "success": True,
            "subscription_id": sub.id,
            "sub_link": sub.sub_link,
        })