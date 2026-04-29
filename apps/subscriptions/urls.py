from django.urls import path
from .views import UserSubscriptionListView, GetPlans

urlpatterns = [
    path("", UserSubscriptionListView.as_view()),
    path('plans/', GetPlans.as_view()),
]