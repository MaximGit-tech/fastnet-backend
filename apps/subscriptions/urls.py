from django.urls import path
from .views import UserSubscriptionListView, GetPlans, RenewSubscriptionView, RegenerateSubIdView

urlpatterns = [
    path("", UserSubscriptionListView.as_view()),
    path('plans/', GetPlans.as_view()),
    path('<int:subscription_id>/renew/', RenewSubscriptionView.as_view()),
    path('<int:subscription_id>/regenerate/', RegenerateSubIdView.as_view()),
]