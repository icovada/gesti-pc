"""
URL configuration for gestipc project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
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
import core.views
from django.contrib import admin
from django.urls import include, path
from tg_bot import urls as tg_bot_urls

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("hr/", include("hr.urls")),
    path("servizio/", include("servizio.urls")),
    path("warehouse/", include("warehouse.urls")),
    path("certificazioni/", include("certifications.urls")),
    path("pcroncellobot/", include(tg_bot_urls)),
    path("", core.views.home, name="home"),
]
