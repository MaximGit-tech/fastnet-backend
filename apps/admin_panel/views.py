import os
import subprocess
from datetime import timedelta
from django.db.models import Sum, Count, Q
from django.utils import timezone
from rest_framework.response import Response
from django.contrib.auth.hashers import check_password
from .auth import AdminAuthMixin
from .models import Admin
from apps.utils.views import CsrfExemptAPIView
from apps.users.models import User
from apps.subscriptions.models import Subscription
from apps.payments.models import Payment
from apps.vpn.panel_client import panel
from rest_framework_simplejwt.tokens import RefreshToken

DE_SSH_HOST = os.getenv("DE_SSH_HOST")
RU_SERVER_IP = os.getenv("RU_SERVER_IP")


class ServerStatsView(AdminAuthMixin, CsrfExemptAPIView):
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

                cpu      = run("top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1")
                mem      = run("free -m | awk 'NR==2{printf \"%s/%s\", $3, $2}'")
                disk     = run("df -h / | awk 'NR==2{printf \"%s/%s\", $3, $2}'")
                uptime   = run("uptime -p")
                ping     = run("ping -c1 -W2 8.8.8.8 | tail -1 | awk '{print $4}' | cut -d'/' -f2")

                net_rx_bytes = run(
                    "cat /proc/net/dev | awk 'NR>2{rx+=$2} END{print rx}'"
                )
                net_tx_bytes = run(
                    "cat /proc/net/dev | awk 'NR>2{tx+=$10} END{print tx}'"
                )

                def bytes_to_gb(b):
                    try:
                        return round(int(b) / (1024 ** 3), 2)
                    except Exception:
                        return 0

                connections = run("ss -tn | grep ESTAB | wc -l")

                vpn_processes = run("pgrep -c xray || pgrep -c v2ray || echo 0")

                return {
                    "status":        "online",
                    "cpu_percent":   cpu,
                    "memory":        mem,
                    "disk":          disk,
                    "uptime":        uptime,
                    "ping_ms":       ping,
                    "net_rx_gb":     bytes_to_gb(net_rx_bytes),
                    "net_tx_gb":     bytes_to_gb(net_tx_bytes),
                    "connections":   connections,
                    "vpn_processes": vpn_processes,
                }
            except Exception as e:
                return {"status": "offline", "error": str(e)}
            finally:
                ssh.close()

        de_stats = get_stats(DE_SSH_HOST, key_path=os.getenv("DE_SSH_KEY_PATH"))
        ru_stats = get_stats(RU_SERVER_IP, key_path=os.getenv("RU_SSH_KEY_PATH"))

        return Response({"de": de_stats, "ru": ru_stats})


class ServerPingView(AdminAuthMixin, CsrfExemptAPIView):
    def get(self, request, server):
        hosts = {"de": DE_SSH_HOST, "ru": RU_SERVER_IP}
        if server not in hosts:
            return Response({"error": "server must be 'de' or 'ru'"}, status=400)

        host = hosts[server]
        try:
            result = subprocess.run(
                ["ping", "-c", "3", "-W", "2", host],
                capture_output=True, text=True, timeout=10
            )
            lines    = result.stdout.strip().split("\n")
            avg_line = [l for l in lines if "avg" in l or "rtt" in l]
            avg_ms   = avg_line[0].split("/")[4] if avg_line else None
            return Response({
                "server":    server,
                "host":      host,
                "reachable": result.returncode == 0,
                "avg_ms":    avg_ms,
            })
        except Exception as e:
            return Response({"server": server, "reachable": False, "error": str(e)})


class UserStatsView(AdminAuthMixin, CsrfExemptAPIView):
    def get(self, request):
        now   = timezone.now()
        today = now.date()

        total          = User.objects.count()
        verified       = User.objects.filter(is_verified=True).count()
        banned         = User.objects.filter(is_banned=True).count()
        trial_used     = User.objects.filter(has_used_trial=True).count()
        with_active    = User.objects.filter(subscriptions__status="active").distinct().count()

        new_today  = User.objects.filter(created_at__date=today).count()
        new_7days  = User.objects.filter(created_at__date__gte=today - timedelta(days=7)).count()
        new_30days = User.objects.filter(created_at__date__gte=today - timedelta(days=30)).count()

        paid_qs        = Payment.objects.filter(status="paid")
        total_revenue  = paid_qs.aggregate(t=Sum("amount_rub"))["t"] or 0
        rev_today      = paid_qs.filter(paid_at__date=today).aggregate(t=Sum("amount_rub"))["t"] or 0
        rev_7days      = paid_qs.filter(paid_at__date__gte=today - timedelta(days=7)).aggregate(t=Sum("amount_rub"))["t"] or 0
        rev_30days     = paid_qs.filter(paid_at__date__gte=today - timedelta(days=30)).aggregate(t=Sum("amount_rub"))["t"] or 0

        return Response({
            "users": {
                "total":           total,
                "verified":        verified,
                "banned":          banned,
                "trial_used":      trial_used,
                "with_active_sub": with_active,
                "new_today":       new_today,
                "new_7days":       new_7days,
                "new_30days":      new_30days,
            },
            "revenue": {
                "total_rub":   total_revenue,
                "today_rub":   rev_today,
                "week_rub":    rev_7days,
                "month_rub":   rev_30days,
            },
        })


class UserListView(AdminAuthMixin, CsrfExemptAPIView):
    def get(self, request):
        status  = request.query_params.get("status")
        search  = request.query_params.get("search", "").strip()
        page    = int(request.query_params.get("page", 1))
        limit   = int(request.query_params.get("limit", 20))
        offset  = (page - 1) * limit

        users = User.objects.annotate(
            active_sub_count=Count("subscriptions", filter=Q(subscriptions__status="active")),
            total_spent=Sum("payment__amount_rub", filter=Q(payment__status="paid")),
        ).order_by("-id")

        if status == "active":
            users = users.filter(subscriptions__status="active").distinct()
        elif status == "banned":
            users = users.filter(is_banned=True)
        elif status == "verified":
            users = users.filter(is_verified=True)
        elif status == "trial":
            users = users.filter(has_used_trial=True)
        elif status == "no_sub":
            users = users.filter(active_sub_count=0)

        if search:
            users = users.filter(
                Q(email__icontains=search) |
                Q(username__icontains=search) |
                Q(full_name__icontains=search)
            )

        total = users.count()
        users = users[offset:offset + limit]

        data = []
        for u in users:
            data.append({
                "id":                  u.id,
                "email":               u.email,
                "telegram_id":         u.telegram_id,
                "username":            u.username,
                "full_name":           u.full_name,
                "is_verified":         u.is_verified,
                "is_banned":           u.is_banned,
                "has_used_trial":      u.has_used_trial,
                "active_subscriptions": u.active_sub_count,
                "total_spent_rub":     u.total_spent or 0,
                "created_at":          u.created_at.isoformat(),
            })

        return Response({"total": total, "page": page, "limit": limit, "users": data})


class UserDetailView(AdminAuthMixin, CsrfExemptAPIView):
    def get(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "Пользователь не найден"}, status=404)

        subscriptions = []
        for sub in user.subscriptions.select_related("plan").order_by("-created_at"):
            traffic = {}
            if sub.panel_uuid:
                try:
                    email   = f"u{user.id}_{sub.id}"
                    traffic = panel.get_client_traffic(email)
                except Exception:
                    traffic = {"up_gb": 0, "down_gb": 0, "total_gb": 0}

            subscriptions.append({
                "id":         sub.id,
                "plan_name":  sub.plan.name,
                "plan_key":   sub.plan.key,
                "status":     sub.status,
                "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
                "sub_link":   sub.sub_link,
                "traffic":    traffic,
                "created_at": sub.created_at.isoformat(),
            })

        payments = []
        total_spent = 0
        for p in Payment.objects.filter(user=user).select_related("plan").order_by("-created_at"):
            if p.status == "paid":
                total_spent += p.amount_rub
            payments.append({
                "id":         p.id,
                "plan":       p.plan.name,
                "status":     p.status,
                "amount_rub": p.amount_rub,
                "method":     p.method,
                "created_at": p.created_at.isoformat(),
                "paid_at":    p.paid_at.isoformat() if p.paid_at else None,
            })

        return Response({
            "id":              user.id,
            "email":           user.email,
            "telegram_id":     user.telegram_id,
            "username":        user.username,
            "full_name":       user.full_name,
            "is_verified":     user.is_verified,
            "is_banned":       user.is_banned,
            "has_used_trial":  user.has_used_trial,
            "created_at":      user.created_at.isoformat(),
            "total_spent_rub": total_spent,
            "keys_total":      len(subscriptions),
            "keys_active":     sum(1 for s in subscriptions if s["status"] == "active"),
            "subscriptions":   subscriptions,
            "payments":        payments,
        })

    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "Пользователь не найден"}, status=404)

        action = request.data.get("action")
        if action == "ban":
            user.is_banned = True
            user.save(update_fields=["is_banned"])
            return Response({"success": True, "is_banned": True})
        elif action == "unban":
            user.is_banned = False
            user.save(update_fields=["is_banned"])
            return Response({"success": True, "is_banned": False})

        return Response({"error": "Неизвестное действие"}, status=400)


class SubscriptionListView(AdminAuthMixin, CsrfExemptAPIView):
    def get(self, request):
        status  = request.query_params.get("status")
        plan    = request.query_params.get("plan")
        page    = int(request.query_params.get("page", 1))
        limit   = int(request.query_params.get("limit", 20))
        offset  = (page - 1) * limit

        subs = Subscription.objects.select_related("user", "plan").order_by("-created_at")

        if status:
            subs = subs.filter(status=status)
        if plan:
            subs = subs.filter(plan__key=plan)

        total = subs.count()
        subs  = subs[offset:offset + limit]

        data = []
        for sub in subs:
            data.append({
                "id":         sub.id,
                "user_id":    sub.user.id,
                "user_email": sub.user.email,
                "telegram_id":sub.user.telegram_id,
                "plan_name":  sub.plan.name,
                "plan_key":   sub.plan.key,
                "status":     sub.status,
                "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
                "sub_link":   sub.sub_link,
                "created_at": sub.created_at.isoformat(),
            })

        return Response({"total": total, "page": page, "limit": limit, "subscriptions": data})


class PaymentStatsView(AdminAuthMixin, CsrfExemptAPIView):
    def get(self, request):
        date_from = request.query_params.get("from")
        date_to   = request.query_params.get("to")
        today     = timezone.now().date()

        paid_qs = Payment.objects.filter(status="paid")

        period_revenue    = None
        period_count      = None
        if date_from and date_to:
            try:
                from datetime import date
                df = date.fromisoformat(date_from)
                dt = date.fromisoformat(date_to)
                period_qs      = paid_qs.filter(paid_at__date__gte=df, paid_at__date__lte=dt)
                period_revenue = period_qs.aggregate(t=Sum("amount_rub"))["t"] or 0
                period_count   = period_qs.count()
            except ValueError:
                return Response({"error": "Неверный формат даты, используй YYYY-MM-DD"}, status=400)

        total_revenue = paid_qs.aggregate(t=Sum("amount_rub"))["t"] or 0
        total_count   = paid_qs.count()

        rev_today  = paid_qs.filter(paid_at__date=today).aggregate(t=Sum("amount_rub"))["t"] or 0
        rev_7days  = paid_qs.filter(paid_at__date__gte=today - timedelta(days=7)).aggregate(t=Sum("amount_rub"))["t"] or 0
        rev_30days = paid_qs.filter(paid_at__date__gte=today - timedelta(days=30)).aggregate(t=Sum("amount_rub"))["t"] or 0

        by_method = list(
            paid_qs.values("method")
            .annotate(total=Sum("amount_rub"), count=Count("id"))
            .order_by("-total")
        )

        by_plan = list(
            paid_qs.values("plan__name", "plan__key")
            .annotate(total=Sum("amount_rub"), count=Count("id"))
            .order_by("-total")
        )

        daily = []
        for i in range(29, -1, -1):
            d   = today - timedelta(days=i)
            rev = paid_qs.filter(paid_at__date=d).aggregate(t=Sum("amount_rub"))["t"] or 0
            cnt = paid_qs.filter(paid_at__date=d).count()
            daily.append({"date": d.isoformat(), "revenue_rub": rev, "count": cnt})

        result = {
            "all_time": {
                "revenue_rub": total_revenue,
                "payments":    total_count,
            },
            "today": {
                "revenue_rub": rev_today,
            },
            "week": {
                "revenue_rub": rev_7days,
            },
            "month": {
                "revenue_rub": rev_30days,
            },
            "by_method": by_method,
            "by_plan":   by_plan,
            "daily_30d": daily,
        }

        if period_revenue is not None:
            result["period"] = {
                "from":        date_from,
                "to":          date_to,
                "revenue_rub": period_revenue,
                "payments":    period_count,
            }

        return result and Response(result)


class PaymentListView(AdminAuthMixin, CsrfExemptAPIView):
    def get(self, request):
        status = request.query_params.get("status")
        page   = int(request.query_params.get("page", 1))
        limit  = int(request.query_params.get("limit", 20))
        offset = (page - 1) * limit

        payments = Payment.objects.select_related("user", "plan").order_by("-created_at")

        if status:
            payments = payments.filter(status=status)

        total    = payments.count()
        payments = payments[offset:offset + limit]

        data = []
        for p in payments:
            data.append({
                "id":          p.id,
                "user_id":     p.user.id,
                "user_email":  p.user.email,
                "telegram_id": p.user.telegram_id,
                "plan_name":   p.plan.name,
                "status":      p.status,
                "amount_rub":  p.amount_rub,
                "method":      p.method,
                "created_at":  p.created_at.isoformat(),
                "paid_at":     p.paid_at.isoformat() if p.paid_at else None,
            })

        return Response({"total": total, "page": page, "limit": limit, "payments": data})


class TrafficStatsView(AdminAuthMixin, CsrfExemptAPIView):
    def get(self, request):
        active_subs  = Subscription.objects.filter(status="active").select_related("user", "plan")
        traffic_list = []

        for sub in active_subs:
            try:
                email   = f"u{sub.user.id}_{sub.id}"
                traffic = panel.get_client_traffic(email)
                if traffic["total_gb"] > 0:
                    traffic_list.append({
                        "user_id":         sub.user.id,
                        "email":           sub.user.email,
                        "telegram_id":     sub.user.telegram_id,
                        "subscription_id": sub.id,
                        "plan_name":       sub.plan.name,
                        "plan_key":        sub.plan.key,
                        "up_gb":           traffic["up_gb"],
                        "down_gb":         traffic["down_gb"],
                        "total_gb":        traffic["total_gb"],
                    })
            except Exception:
                continue

        traffic_list.sort(key=lambda x: x["total_gb"], reverse=True)

        total_gb    = round(sum(t["total_gb"]   for t in traffic_list), 2)
        total_up    = round(sum(t["up_gb"]      for t in traffic_list), 2)
        total_down  = round(sum(t["down_gb"]    for t in traffic_list), 2)

        return Response({
            "total_traffic_gb":    total_gb,
            "total_upload_gb":     total_up,
            "total_download_gb":   total_down,
            "active_subscriptions": active_subs.count(),
            "top5":                traffic_list[:5],
            "all":                 traffic_list,
        })
    

class AdminLoginView(CsrfExemptAPIView):
    def post(self, request):
        email    = request.data.get("email", "").strip().lower()
        password = request.data.get("password", "")

        try:
            admin = Admin.objects.get(email=email, is_active=True)
        except Admin.DoesNotExist:
            return Response({"error": "Неверный email или пароль"}, status=401)

        if not check_password(password, admin.password):
            return Response({"error": "Неверный email или пароль"}, status=401)

        admin.last_login = timezone.now()
        admin.save(update_fields=["last_login"])

        refresh = RefreshToken()
        refresh["role"]     = "admin"
        refresh["admin_id"] = admin.id
        refresh["name"]     = admin.name

        return Response({
            "access":  str(refresh.access_token),
            "refresh": str(refresh),
            "name":    admin.name,
            "email":   admin.email,
        })


class AdminRefreshView(CsrfExemptAPIView):
    def post(self, request):
        from rest_framework_simplejwt.tokens import RefreshToken as RT
        token_str = request.data.get("refresh", "")
        try:
            refresh = RT(token_str)
            if refresh.get("role") != "admin":
                raise ValueError
            return Response({"access": str(refresh.access_token)})
        except Exception:
            return Response({"error": "Недействительный токен"}, status=401)


class AdminMeView(AdminAuthMixin, CsrfExemptAPIView):
    def get(self, request):
        try:
            admin = Admin.objects.get(id=request.admin_id)
        except Admin.DoesNotExist:
            return Response({"error": "Not found"}, status=404)
        return Response({
            "id":         admin.id,
            "name":       admin.name,
            "email":      admin.email,
            "last_login": admin.last_login.isoformat() if admin.last_login else None,
        })
