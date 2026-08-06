from django.db import models

class Admin(models.Model):
    email      = models.EmailField(unique=True)
    name       = models.CharField(max_length=64)
    password   = models.CharField(max_length=128)
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "admins"

    def __str__(self):
        return f"{self.name} ({self.email})"
