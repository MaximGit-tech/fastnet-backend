import os
from rest_framework.permissions import BasePermission

class BotSecretPermission(BasePermission):
    def has_permission(self, request, view):
        secret = request.headers.get("X-Bot-Secret")
        return secret == os.getenv("BOT_SECRET")