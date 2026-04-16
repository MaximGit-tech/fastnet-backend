from django.db import models
import secrets


class User(models.Model):
    email       = models.EmailField(unique=True)
    is_verified = models.BooleanField(default=False)
    telegram_id = models.BigIntegerField(unique=True, null=True, blank=True)
    username    = models.CharField(max_length=64, blank=True)
    full_name   = models.CharField(max_length=128, blank=True)
    link_token  = models.CharField(max_length=64, blank=True, db_index=True)
    is_banned   = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
    balance     = models.IntegerField()

    class Meta:
        db_table = "users"

    def generate_link_token(self) -> str:
        self.link_token = secrets.token_urlsafe(32)
        self.save(update_fields=["link_token"])
        return self.link_token

    def __str__(self):
        return f"User {self.email} with balance: {self.balance}"


class EmailVerification(models.Model):
    user       = models.ForeignKey(User, on_delete=models.CASCADE,
                                    related_name="verifications")
    code       = models.CharField(max_length=6)
    expires_at = models.DateTimeField()
    is_used    = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "email_verifications"