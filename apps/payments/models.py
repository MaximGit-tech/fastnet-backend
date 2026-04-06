from django.db import models
from apps.users.models import TelegramUser
from apps.subscriptions.models import Subscription, Plan

class Payment(models.Model):
    METHOD_CHOICES = [
        ("manual", "СБП/Карта (ручное)"),
        ("stars",  "Telegram Stars"),
        ("crypto", "Криптовалюта"),
    ]
    STATUS_CHOICES = [
        ("pending",  "Ожидает"),
        ("paid",     "Оплачен"),
        ("failed",   "Ошибка"),
        ("rejected", "Отклонён"),
        ("expired",  "Истёк"),
    ]

    user = models.ForeignKey(TelegramUser,
                             on_delete=models.CASCADE)
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    subscription = models.ForeignKey(Subscription,
                                     on_delete=models.SET_NULL,
                                     null=True, blank=True)
    method = models.CharField(max_length=16,
                              choices=METHOD_CHOICES)
    status = models.CharField(max_length=16,
                              choices=STATUS_CHOICES,
                              default="pending")
    amount_rub = models.IntegerField(default=0)
    amount_stars = models.IntegerField(default=0)
    amount_crypto = models.DecimalField(max_digits=18,
                                        decimal_places=8,
                                        default=0)
    crypto_currency = models.CharField(max_length=10, blank=True)
    provider_charge_id = models.CharField(max_length=128, blank=True)
    confirmed_by = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "payments"
