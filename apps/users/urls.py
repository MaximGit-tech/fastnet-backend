from django.urls import path
from .views import RegisterOrGetUserView


urlpatterns = [
    path("register-or-get/", RegisterOrGetUserView.as_view(), name='register-or-get')
]