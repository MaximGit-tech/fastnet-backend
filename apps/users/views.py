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
from ..utils.activate_sub import activate_subscription

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

        trial_sub  = None
        trial_link = None

        if not user.has_used_trial:
            from apps.subscriptions.trial import activate_trial
            from apps.utils.bot_notify import notify_bot

            trial_sub = activate_trial(user)
            if trial_sub:
                trial_link = trial_sub.sub_link
                notify_bot(user, "trial_activated", {
                    "sub_link":   trial_link,
                    "expires_at": trial_sub.expires_at.isoformat(),
                })


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
    GET /api/v1/users/me/
    """
    def get(self, request):
        user, err = get_user_from_request(request)
        if err:
            return err

        return Response({
            "user_id":     user.id,
            "email":       user.email,
            "is_verified": user.is_verified,
            "is_banned":   user.is_banned,
            "telegram_id": user.telegram_id,
        })
        
class WebLoginView(CsrfExemptAPIView):
    """
    POST /api/v1/users/web/login/
    """
    def post(self, request):
        email = request.data.get("email", "").lower().strip()

        if not email or "@" not in email:
            return Response({"error": "Некорректный email"}, status=400)

        user, _ = User.objects.get_or_create(email=email)

        if user.is_banned:
            return Response({"error": "Аккаунт заблокирован"}, status=403)

        last = EmailVerification.objects.filter(
            user=user, is_used=False
        ).order_by("-created_at").first()

        if last and (timezone.now() - last.created_at).total_seconds() < 60:
            return Response({"error": "Подождите минуту перед повторной отправкой"}, status=429)

        code = generate_code()
        EmailVerification.objects.filter(user=user, is_used=False).update(is_used=True)

        html = render_to_string("verification_code.html", {"code": code})
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

        return Response({"user_id": user.id})


class WebVerifyView(CsrfExemptAPIView):
    """
    POST /api/v1/users/web/verify/
    """
    def post(self, request):
        from rest_framework_simplejwt.tokens import RefreshToken

        user_id = request.data.get("user_id")
        code = request.data.get("code", "").strip()

        if not user_id or not code:
            return Response({"error": "user_id и code обязательны"}, status=400)

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "Пользователь не найден"}, status=404)

        if user.is_banned:
            return Response({"error": "Аккаунт заблокирован"}, status=403)

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
        user.save(update_fields=["is_verified"])

        refresh = RefreshToken()
        refresh["user_id"] = user.id
        refresh["email"] = user.email

        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user_id": user.id,
            "email": user.email,
        })


class WebRefreshView(CsrfExemptAPIView):
    """
    POST /api/v1/users/web/refresh/
    """
    def post(self, request):
        from rest_framework_simplejwt.tokens import RefreshToken
        from rest_framework_simplejwt.exceptions import TokenError

        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response({"error": "refresh обязателен"}, status=400)

        try:
            refresh = RefreshToken(refresh_token)
            return Response({"access": str(refresh.access_token)})
        except TokenError:
            return Response({"error": "Невалидный или истёкший токен"}, status=401)
    




