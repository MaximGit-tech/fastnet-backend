from django.db import models
from apps.users.models import User
from apps.subscriptions.models import Subscription, Plan

class Payment(models.Model):
    STATUS_CHOICES = [
        ("pending",  "Ожидает"),
        ("paid",     "Оплачен"),
        ("failed",   "Ошибка"),
        ("rejected", "Отклонён"),
        ("expired",  "Истёк"),
    ]

    user = models.ForeignKey(User,
                             on_delete=models.CASCADE)
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    subscription = models.ForeignKey(Subscription,
                                     on_delete=models.SET_NULL,
                                     null=True, blank=True)
    status = models.CharField(max_length=16,
                              choices=STATUS_CHOICES,
                              default="pending")
    amount_rub = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "payments"
