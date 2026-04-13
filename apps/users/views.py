from rest_framework.views import APIView
from .models import TelegramUser
from requests import Response


class RegisterOrGetUserView(APIView):
    """POST /api/v1/users/register/"""

    def post(self, request):
        user, _ = TelegramUser.objects.update_or_create(
            telegram_id=request.data.get('telegram_id'),
            defaults={
                'username': request.data.get('username', ''),
                'full_name': request.data.get('full_name', ''),
            }
        )
        return Response({
            'telegram_id': user.telegram_id,
            'username': user.username,
            'id_banned': user.is_banned,
        })
