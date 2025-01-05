from django.contrib import admin
from django.urls import path, include
from django.core.exceptions import PermissionDenied



urlpatterns = [
    path('bossmankun/login/', lambda request: (_ for _ in ()).throw(PermissionDenied)),
    path('bossmankun/', admin.site.urls),
    path('', include('base.urls')),
    path('', include('automations.urls')),
]  
