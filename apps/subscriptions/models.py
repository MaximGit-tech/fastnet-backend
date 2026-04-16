from django.db import models
from apps.users.models import User
import os

class Plan(models.Model):
    key = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=64)
    days = models.IntegerField()
    price_rub = models.IntegerField()
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "plans"

    def __str__(self):
        return f"{self.name} ({self.key})"


class Subscription(models.Model):
    STATUS_CHOICES = [
        ("pending",   "Ожидает активации"),
        ("active",    "Активна"),
        ("expired",   "Истекла"),
        ("cancelled", "Отменена"),
    ]

    user = models.ForeignKey(User,
                            on_delete=models.CASCADE,
                            related_name="subscriptions")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    status = models.CharField(max_length=16,
                             choices=STATUS_CHOICES,
                             default="pending")
    panel_uuid = models.CharField(max_length=36, blank=True)
    sub_id = models.CharField(max_length=32, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "subscriptions"

    @property
    def sub_link(self) -> str:
        base = os.getenv("SUB_BASE_URL", "")
        return f"{base}/{self.sub_id}" if self.sub_id else ""

    @property
    def traffic_used_gb(self) -> float:
        return 0.0

    def __str__(self):
        return f"{self.user} — {self.plan.name} ({self.status})"
    


