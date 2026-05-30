import os
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import AccessToken

ADMIN_JWT_SECRET = os.getenv("ADMIN_JWT_SECRET", "change_me")


class AdminAuthMixin:
    def dispatch(self, request, *args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return Response({"error": "Unauthorized"}, status=401)
        try:
            token = AccessToken(auth[7:])
            if token.get("role") != "admin":
                raise ValueError("not admin")
            request.admin_id = token["admin_id"]
        except Exception:
            return Response({"error": "Unauthorized"}, status=401)
        return super().dispatch(request, *args, **kwargs)