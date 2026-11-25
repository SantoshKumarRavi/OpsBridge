from django.contrib import admin
from django.urls import include,path
from onboarding.views import health
urlpatterns=[path('admin/',admin.site.urls),path('health',health),path('api/v1/',include('onboarding.urls'))]
