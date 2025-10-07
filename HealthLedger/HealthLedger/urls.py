"""
URL configuration for HealthLedger project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
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
from django.contrib import admin
from django.urls import path
from . import views
from django.http import HttpResponse
urlpatterns = [
    path('admin/', admin.site.urls),
    path("", views.DASH, name="Dashboard"),
    path('new_record/', views.CREATE, name='home'),
    path('update_record/', views.UPDATE, name='update'),
    path('view_all/', views.VIEW_ALL, name='view_all'),
    
    
    # APIS
    path('api/get_data_by_uid', views.get_data_by_uid, name='get_data_by_uid'),
    path('api/update_payment/', views.update_payment, name='update_payment'),
    path('api/load_data/', views.load_data, name='load_data'),
    path('api/recent-activity/', views.recent_activity, name='recent_activity'),
    path('api/get_stats/', views.getstats, name='get_stats'),
    path('api/add_new_data/', views.ADD_NEW_DATA, name='add_new_data'),
    
    
    path('.well-known/appspecific/com.chrome.devtools.json', lambda r: HttpResponse('{}', content_type='application/json')),
]
