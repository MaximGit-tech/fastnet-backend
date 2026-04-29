from django.urls import path
from .views import UserSubscriptionListView

urlpatterns = [
    path("", UserSubscriptionListView.as_view()),
]