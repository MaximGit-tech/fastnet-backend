import os
import subprocess
from rest_framework.response import Response
from apps.utils.views import CsrfExemptAPIView
from apps.users.models import User
from apps.subscriptions.models import Subscription
from apps.payments.models import Payment
from apps.vpn.panel_client import panel

DE_SSH_HOST = os.getenv("DE_SSH_HOST")
RU_SERVER_IP = os.getenv("RU_SERVER_IP")


class ServerStatsView(CsrfExemptAPIView):
    """
    GET /api/v1/admin/servers/stats/
    """
    def get(self, request):
        import paramiko

        def get_stats(host, key_path=None, password=None):
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                if key_path:
                    ssh.connect(host, username="root", key_filename=key_path, timeout=8)
                else:
                    ssh.connect(host, username="root", password=password, timeout=8)

                def run(cmd):
                    _, stdout, _ = ssh.exec_command(cmd)
                    return stdout.read().decode().strip()

                cpu = run("top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1")
                mem = run("free -m | awk 'NR==2{printf \"%s/%s\", $3, $2}'")
                disk = run("df -h / | awk 'NR==2{printf \"%s/%s\", $3, $2}'")
                uptime = run("uptime -p")
                ping = run("ping -c1 -W2 8.8.8.8 | tail -1 | awk '{print $4}' | cut -d'/' -f2")
                return {
                    "status": "online",
                    "cpu_percent": cpu,
                    "memory": mem,
                    "disk": disk,
                    "uptime": uptime,
                    "ping_ms": ping,
                }
            except Exception as e:
                return {"status": "offline", "error": str(e)}
            finally:
                ssh.close()

        de_stats = get_stats(DE_SSH_HOST, key_path=os.getenv("DE_SSH_KEY_PATH"))
        ru_stats = get_stats(RU_SERVER_IP, key_path=os.getenv("RU_SSH_KEY_PATH"))

        return Response({"de": de_stats, "ru": ru_stats})


class ServerPingView(CsrfExemptAPIView):
    """
    GET /api/v1/admin/servers/{server}/ping/
    """
    def get(self, request, server):
        hosts = {"de": DE_SSH_HOST, "ru": RU_SERVER_IP}
        if server not in hosts:
            return Response({"error": "server must be list"}, status=400)

        host = hosts[server]
        try:
            result = subprocess.run(
                ["ping", "-c", "3", "-W", "2", host],
                capture_output=True, text=True, timeout=10
            )
            lines = result.stdout.strip().split("\n")
            avg_line = [l for l in lines if "avg" in l or "rtt" in l]
            avg_ms = avg_line[0].split("/")[4] if avg_line else None
            return Response({
                "server": server,
                "host": host,
                "reachable": result.returncode == 0,
                "avg_ms": avg_ms,
            })
        except Exception as e:
            return Response({"server": server, "reachable": False, "error": str(e)})


class UserStatsView(CsrfExemptAPIView):
    """
    GET /api/v1/admin/users/stats/
    """
    def get(self, request):
        total = User.objects.count()
        verified = User.objects.filter(is_verified=True).count()
        banned = User.objects.filter(is_banned=True).count()
        with_active_sub = User.objects.filter(
            subscriptions__status="active"
        ).distinct().count()

        total_revenue = Payment.objects.filter(
            status="paid"
        ).aggregate(
            total=__import__("django.db.models", fromlist=["Sum"]).Sum("amount_rub")
        )["total"] or 0

        return Response({
            "total_users": total,
            "verified_users": verified,
            "banned_users": banned,
            "users_with_active_sub": with_active_sub,
            "total_revenue_rub": total_revenue,
        })


class UserListView(CsrfExemptAPIView):
    """
    GET /api/v1/admin/users/?status=active&page=1&limit=20
    """
    def get(self, request):
        status = request.query_params.get("status")
        page = int(request.query_params.get("page", 1))
        limit = int(request.query_params.get("limit", 20))
        offset = (page - 1) * limit

        users = User.objects.all().order_by("-id")

        if status == "active":
            users = users.filter(subscriptions__status="active").distinct()
        elif status == "banned":
            users = users.filter(is_banned=True)
        elif status == "verified":
            users = users.filter(is_verified=True)

        total = users.count()
        users = users[offset:offset + limit]

        data = []
        for u in users:
            active_subs = u.subscriptions.filter(status="active").count()
            data.append({
                "id": u.id,
                "email": u.email,
                "telegram_id": u.telegram_id,
                "username": u.username,
                "full_name": u.full_name,
                "is_verified": u.is_verified,
                "is_banned": u.is_banned,
                "active_subscriptions": active_subs,
                "created_at": u.created_at.isoformat(),
            })

        return Response({"total": total, "page": page, "limit": limit, "users": data})


class UserDetailView(CsrfExemptAPIView):
    """
    GET /api/v1/admin/users/{user_id}/
    """
    def get(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "Пользователь не найден"}, status=404)

        subscriptions = []
        for sub in user.subscriptions.select_related("plan").all():
            traffic = {}
            if sub.panel_uuid:
                try:
                    email = f"u{user.id}_{sub.id}"
                    traffic = panel.get_client_traffic(email)
                except Exception:
                    traffic = {"up_gb": 0, "down_gb": 0, "total_gb": 0}

            subscriptions.append({
                "id": sub.id,
                "plan_name": sub.plan.name,
                "status": sub.status,
                "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
                "sub_link": sub.sub_link,
                "traffic": traffic,
                "created_at": sub.created_at.isoformat(),
            })

        payments = []
        for p in Payment.objects.filter(user=user).order_by("-created_at")[:10]:
            payments.append({
                "id": p.id,
                "plan": p.plan.name,
                "status": p.status,
                "amount_rub": p.amount_rub,
                "method": p.method,
                "created_at": p.created_at.isoformat(),
                "paid_at": p.paid_at.isoformat() if p.paid_at else None,
            })

        return Response({
            "id": user.id,
            "email": user.email,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "full_name": user.full_name,
            "is_verified": user.is_verified,
            "is_banned": user.is_banned,
            "created_at": user.created_at.isoformat(),
            "subscriptions": subscriptions,
            "payments": payments,
        })


class SubscriptionListView(CsrfExemptAPIView):
    """
    GET /api/v1/admin/subscriptions/?status=active&page=1&limit=20
    """
    def get(self, request):
        status = request.query_params.get("status")
        page = int(request.query_params.get("page", 1))
        limit = int(request.query_params.get("limit", 20))
        offset = (page - 1) * limit

        subs = Subscription.objects.select_related("user", "plan").order_by("-created_at")

        if status:
            subs = subs.filter(status=status)

        total = subs.count()
        subs = subs[offset:offset + limit]

        data = []
        for sub in subs:
            data.append({
                "id": sub.id,
                "user_id": sub.user.id,
                "user_email": sub.user.email,
                "telegram_id": sub.user.telegram_id,
                "plan_name": sub.plan.name,
                "status": sub.status,
                "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
                "sub_link": sub.sub_link,
                "created_at": sub.created_at.isoformat(),
            })

        return Response({"total": total, "page": page, "limit": limit, "subscriptions": data})


class TrafficStatsView(CsrfExemptAPIView):
    """
    GET /api/v1/admin/traffic/
    """
    def get(self, request):
        active_subs = Subscription.objects.filter(
            status="active"
        ).select_related("user", "plan")

        traffic_list = []
        for sub in active_subs:
            try:
                email = f"u{sub.user.id}_{sub.id}"
                traffic = panel.get_client_traffic(email)
                if traffic["total_gb"] > 0:
                    traffic_list.append({
                        "user_id": sub.user.id,
                        "email": sub.user.email,
                        "telegram_id": sub.user.telegram_id,
                        "subscription_id": sub.id,
                        "plan_name": sub.plan.name,
                        "up_gb": traffic["up_gb"],
                        "down_gb": traffic["down_gb"],
                        "total_gb": traffic["total_gb"],
                    })
            except Exception:
                continue

        traffic_list.sort(key=lambda x: x["total_gb"], reverse=True)
        top5 = traffic_list[:5]

        total_gb = round(sum(t["total_gb"] for t in traffic_list), 2)

        return Response({
            "total_traffic_gb": total_gb,
            "active_subscriptions": active_subs.count(),
            "top5": top5,
        })