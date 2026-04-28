from django.urls import path
from .views import SubscriptionListView

urlpatterns = [
    path("", SubscriptionListView.as_view()),
]