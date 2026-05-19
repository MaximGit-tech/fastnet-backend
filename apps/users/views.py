import random
import string
import resend
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from rest_framework.response import Response
from apps.utils.views import CsrfExemptAPIView
from .models import User, EmailVerification
from django.template.loader import render_to_string
from apps.utils.authentication import get_user_from_request

resend.api_key = settings.RESEND_API_KEY


def generate_code() -> str:
    return "".join(random.choices(string.digits, k=6))


class RegisterView(CsrfExemptAPIView):
    """
    POST /api/v1/users/register/
    """
    def post(self, request):
        email = request.data.get("email", "").lower().strip()

        if not email or "@" not in email:
            return Response({"error": "Некорректный email"}, status=400)

        user, created = User.objects.get_or_create(email=email)

        if user.is_verified and user.telegram_id:
            return Response({
                "user_id":        user.id,
                "already_exists": True,
                "is_verified":    True,
            })

        code = generate_code()

        EmailVerification.objects.filter(user=user, is_used=False).update(is_used=True)

        html = render_to_string(
            "verification_code.html",
            {"code": code}
        )
        EmailVerification.objects.create(
            user=user,
            code=code,
            expires_at=timezone.now() + timedelta(minutes=10)
        )

        resend.Emails.send({
            "from": settings.EMAIL_FROM,
            "to": [user.email],
            "subject": "FastNet код подтверждения",
            "html": html
        })

        return Response({
            "user_id":        user.id,
            "already_exists": not created,
            "is_verified":    False,
        })


class VerifyEmailView(CsrfExemptAPIView):
    """
    POST /api/v1/users/verify-email/
    """
    def post(self, request):
        user_id     = request.data.get("user_id")
        code        = request.data.get("code", "").strip()
        telegram_id = request.data.get("telegram_id")
        username    = request.data.get("username", "")
        full_name   = request.data.get("full_name", "")

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "Пользователь не найден"}, status=404)

        verification = EmailVerification.objects.filter(
            user=user,
            code=code,
            is_used=False,
            expires_at__gt=timezone.now()
        ).order_by("-created_at").first()

        if not verification:
            return Response({"error": "Неверный или истёкший код"}, status=400)

        verification.is_used = True
        verification.save()

        user.is_verified = True
        user.telegram_id = telegram_id
        user.username    = username
        user.full_name   = full_name
        user.save()

        link_token = user.generate_link_token()

        return Response({
            "success":    True,
            "user_id":    user.id,
            "email":      user.email,
            "link_token": link_token,
        })


class ResendCodeView(CsrfExemptAPIView):
    """
    POST /api/v1/users/resend-code/
    """
    def post(self, request):
        user_id = request.data.get("user_id")

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "Не найден"}, status=404)

        last = EmailVerification.objects.filter(
            user=user,
            is_used=False
        ).order_by("-created_at").first()

        if last and (timezone.now() - last.created_at).total_seconds() < 60:
            return Response(
                {"error": "Подождите минуту перед повторной отправкой"},
                status=429
            )

        code = generate_code()

        EmailVerification.objects.filter(user=user, is_used=False).update(is_used=True)

        html = render_to_string(
            "verification_code.html",
            {"code": code}
        )
        EmailVerification.objects.create(
            user=user,
            code=code,
            expires_at=timezone.now() + timedelta(minutes=10)
        )

        resend.Emails.send({
            "from": settings.EMAIL_FROM,
            "to": [user.email],
            "subject": "FastNet код подтверждения",
            "html": html
        })

        return Response({"success": True})


class GetUserView(CsrfExemptAPIView):
    """
    GET /api/v1/users/me/?telegram_id=123
    """
    def get(self, request):
        telegram_id = request.query_params.get("telegram_id")

        if not telegram_id:
            return Response({"error": "telegram_id обязателен"}, status=400)

        try:
            user = User.objects.get(telegram_id=telegram_id)
            return Response({
                "user_id":     user.id,
                "email":       user.email,
                "is_verified": user.is_verified,
                "is_banned":   user.is_banned,
                "telegram_id": user.telegram_id,
            })
        except User.DoesNotExist:
            return Response({"error": "Не найден"}, status=404)
    




