from django.urls import path, include
from django.http import HttpResponse
import traceback

def handler500(request):
    tb = traceback.format_exc()
    return HttpResponse(f"<pre>{tb}</pre>", status=500)

urlpatterns = [
    path('api/v1/payment/', include('apps.payments.urls')),
    path('api/v1/users/', include('apps.users.urls')),
]

handler500 = handler500
