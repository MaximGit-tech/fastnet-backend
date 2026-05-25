import os

from django.contrib.auth.models import AnonymousUser
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError
from apps.users.models import User


class BotSecretAuthentication(BaseAuthentication):
    def authenticate(self, request):
        secret = request.headers.get("X-Bot-Secret")

        if not secret:
            return None

        if secret != os.getenv("BOT_SECRET"):
            raise AuthenticationFailed("Invalid bot secret")

        return (AnonymousUser(), None)
    

def get_user_from_request(request):
    auth = request.headers.get("Authorization", "")

    if auth.startswith("Bearer "):
        try:
            token = AccessToken(auth.split(" ")[1])
            user = User.objects.get(id=token["user_id"])
            return user, None
        except (TokenError, User.DoesNotExist):
            from rest_framework.response import Response
            return None, Response({"error": "Невалидный токен"}, status=401)

    bot_secret = request.headers.get("X-Bot-Secret")
    if bot_secret:
        if bot_secret != os.getenv("BOT_SECRET"):
            from rest_framework.response import Response
            return None, Response({"error": "Неверный bot secret"}, status=403)

        email = request.query_params.get("email") or request.data.get("email")
        telegram_id = request.query_params.get("telegram_id") or request.data.get("telegram_id")

        if email:
            try:
                user = User.objects.get(email=email)
                return user, None
            except User.DoesNotExist:
                from rest_framework.response import Response
                return None, Response({"error": "Пользователь не найден"}, status=404)

        if telegram_id:
            try:
                user = User.objects.get(telegram_id=telegram_id)
                return user, None
            except User.DoesNotExist:
                from rest_framework.response import Response
                return None, Response({"error": "Пользователь не найден"}, status=404)

        from rest_framework.response import Response
        return None, Response({"error": "email или telegram_id обязателен"}, status=400)

    from rest_framework.response import Response
    return None, Response({"error": "Требуется авторизация"}, status=401)