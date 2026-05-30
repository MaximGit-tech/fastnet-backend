from django.db import models
import secrets


class User(models.Model):
    email                = models.EmailField(unique=True)
    is_verified          = models.BooleanField(default=False)
    telegram_id          = models.BigIntegerField(unique=True, null=True, blank=True)
    username             = models.CharField(max_length=64, blank=True)
    full_name            = models.CharField(max_length=128, blank=True)
    link_token           = models.CharField(max_length=64, blank=True, db_index=True)
    is_banned            = models.BooleanField(default=False)
    has_used_trial       = models.BooleanField(default=False)

    referred_by          = models.ForeignKey(
        "self", null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="referrals"
    )
    ref_token_bot        = models.CharField(max_length=64, blank=True, null=True, unique=True, db_index=True)
    ref_token_web        = models.CharField(max_length=64, blank=True, null=True, unique=True, db_index=True)
    referral_bonus_given = models.BooleanField(default=False)

    created_at           = models.DateTimeField(auto_now_add=True)
    updated_at           = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "users"

    def generate_link_token(self) -> str:
        self.link_token = secrets.token_urlsafe(32)
        self.save(update_fields=["link_token"])
        return self.link_token

    def generate_ref_tokens(self) -> None:
        if not self.ref_token_bot:
            self.ref_token_bot = secrets.token_urlsafe(24)
        if not self.ref_token_web:
            self.ref_token_web = secrets.token_urlsafe(24)
        self.save(update_fields=["ref_token_bot", "ref_token_web"])

    def __str__(self):
        return f"User {self.email}"


class EmailVerification(models.Model):
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name="verifications")
    code       = models.CharField(max_length=6)
    expires_at = models.DateTimeField()
    is_used    = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "email_verifications"