from django.db import models

class TelegramUser(models.Model):
    telegram_id = models.BigIntegerField(unique=True)
    username = models.CharField(max_length=64, blank=True)
    full_name = models.CharField(max_length=128, blank=True)
    is_banned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "telegram_users"

    def __str__(self):
        return f"@{self.username} ({self.telegram_id})"
