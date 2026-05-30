from django.urls import path
from .views import GetRefLinksView, GetReferrerInfoView, RegisterView, VerifyEmailView, ResendCodeView, GetUserView, WebLoginView, WebVerifyView, WebRefreshView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('verify-email/', VerifyEmailView.as_view(), name='verify'),
    path('resend-code/', ResendCodeView.as_view(), name='resend'),
    path('me/', GetUserView.as_view(), name='me'),
    path('web/login/', WebLoginView.as_view(), name='web-login'),
    path('web/verify/', WebVerifyView.as_view(), name='web-verify'),
    path('web/refresh/', WebRefreshView.as_view(), name='web-refresh'),
    path("ref-links/",      GetRefLinksView.as_view()),
    path("referrer-info/",  GetReferrerInfoView.as_view()),
]