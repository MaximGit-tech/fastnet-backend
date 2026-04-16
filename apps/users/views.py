from .models import User
from rest_framework.response import Response
from apps.utils.views import CsrfExemptAPIView


class RegisterOrGetUserView(CsrfExemptAPIView):
    """POST /api/v1/users/register-or-get/"""

    def post(self, request):
        user, _ = User.objects.update_or_create(
            telegram_id=request.data.get('telegram_id'),
            defaults={
                'username': request.data.get('username', ''),
                'full_name': request.data.get('full_name', ''),
            }
        )
        return Response({
            'telegram_id': user.telegram_id,
            'username': user.username,
            'is_banned': user.is_banned,
        })
