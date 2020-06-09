"""nyc_data URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.contrib import admin
from django.urls import path, include

from django_otp.admin import OTPAdminSite

import ppe

if not settings.INSECURE_MODE:
    otp_admin_site = OTPAdminSite(OTPAdminSite.name)
    for model_cls, model_admin in admin.site._registry.items():
        otp_admin_site.register(model_cls, model_admin.__class__)

def trigger_error(request):
    division_by_zero = 1 / 0

urlpatterns = [
    path("admax/", admin.site.urls if settings.INSECURE_MODE else otp_admin_site.urls),
    path("accounts/", include("allauth.urls")),
    path("", include("ppe.urls")),
    path("sentry-debug/", trigger_error),
]
