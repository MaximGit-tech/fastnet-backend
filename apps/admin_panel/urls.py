from django.urls import path
from .views import (
    ServerStatsView,
    ServerPingView,
    UserStatsView,
    UserListView,
    UserDetailView,
    SubscriptionListView,
    PaymentStatsView,
    PaymentListView,
    TrafficStatsView,
)

urlpatterns = [
    path("servers/stats/",              ServerStatsView.as_view()),
    path("servers/<str:server>/ping/",  ServerPingView.as_view()),
    path("users/stats/",                UserStatsView.as_view()),
    path("users/",                      UserListView.as_view()),
    path("users/<int:user_id>/",        UserDetailView.as_view()),
    path("subscriptions/",             SubscriptionListView.as_view()),
    path("payments/stats/",            PaymentStatsView.as_view()),
    path("payments/",                  PaymentListView.as_view()),
    path("traffic/",                   TrafficStatsView.as_view()),
]