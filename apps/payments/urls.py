from django.urls import path
from .views import YookassaPaymentCreateView, YookassaWebhookView

urlpatterns = [
    path('yookassa/create/', YookassaPaymentCreateView.as_view(), name='create-yookassa-payment'),
    path('yookassa/webhook/', YookassaWebhookView.as_view(), name='yookassa-webhook'),
]