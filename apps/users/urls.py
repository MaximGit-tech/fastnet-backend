from django.urls import path
from .views import RegisterView, VerifyEmailView, ResendCodeView, GetUserView


urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('verify-email/', VerifyEmailView.as_view(), name='verify'),
    path('resend-code/', ResendCodeView.as_view(), name='resend'),
    path('me/', GetUserView.as_view(), name='me'),
]