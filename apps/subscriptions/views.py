from apps.utils.views import CsrfExemptAPIView
from rest_framework.response import Response
from apps.users.models import User
from .models import Subscription, Plan


class UserSubscriptionListView(CsrfExemptAPIView):
    """
    GET /api/v1/subscriptions/?telegram_id=1234567
    Возвращает все активные подписки пользователя с ключами
    """
    def get(self, request):
        telegram_id = request.query_params.get('telegram_id')

        if not telegram_id:
            return Response({'error': 'telegram_id is required'}, status=400)
        
        try:
            user = User.objects.get(telegram_id=telegram_id)
        except User.DoesNotExist:
            return Response({'error': 'user does not exist'}, status=404)
        
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
        plans = Plan.objects.filter(is_active=True).order_by('-price_rub')

        return Response([{
            'plan_name': p.name,
            'days': p.days,
            'price_rub': p.price_rub
        } for p in plans])