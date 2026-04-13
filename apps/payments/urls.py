from django.urls import path
from views import SBPPaymentCreateView, YookassaWebhookView

urlpatterns = [
    path('yookassa/create/', SBPPaymentCreateView.as_view(), name='create-yookassa-payment'),
    path('yookassa/create/', YookassaWebhookView.as_view(), name='yookassa-webhook'),
]