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
    # Management Paths
    path('admin/', admin.site.urls),
    path("", views.DASH, name="Dashboard"),
    path('new_record/', views.CREATE, name='home'),
    path('update_record/', views.UPDATE, name='update'),
    path('view_all/', views.VIEW_ALL, name='view_all'),
    path('print/<str:invoice_num>/', views.PRINT_INVOICE, name='print_invoice'),
    path('login/', views.LOGIN, name='login'),
    path('logout/', views.LOGOUT, name='logout'),
    path('logout/<str:status>/', views.LOGOUT_HARD, name='logout_hard'),
    
    # User Paths
    path('login/patient/', views.user_login, name='user_login'),
    path('user/<str:user_email>/', views.user_dashboard, name='user_dashboard'),
    path('user/<str:user_email>/invoices/', views.user_invoices, name='user_invoices'),
    # API to fetch invoices for a specific user (email is base64 encoded in the path)
    path('api/user/invoices/<str:user_email>/', views.api_user_invoices, name='api_user_invoices'),
    
    # APIS
    path('api/get_data_by_uid', views.get_data_by_uid, name='get_data_by_uid'),
    path('api/get_data_by_invoice_id', views.get_data_by_invoice_id, name='get_data_by_invoice_id'),
    path('api/update_payment/', views.update_payment, name='update_payment'),
    
    path('api/load_data/', views.load_data, name='load_data'),
    path('api/recent-activity/', views.recent_activity, name='recent_activity'),
    path('api/get_stats/', views.getstats, name='get_stats'),
    path('api/add_new_data/', views.add_new_data_row, name='add_new_data'),
    path('api/invoice/<str:invoice_num>/', views.detailed_invoice_view, name='detailed_invoice'),
    path('api/records/', views.load_data, name='api_records'),
    path('api/records/count/', views.records_count, name='api_records_count'),
    path('api/user/payment/<str:amount>/', views.user_payment, name='api_user_payment'),
    
    # Razorpay Payment Window
    path('razorpay_payment/', views.razorpay_payment_window, name='razorpay_payment_window'),
    path('api/initiate_payment/', views.initiate_payment, name='initiate_payment'),
    path('api/verify_payment/', views.verify_payment, name='verify_payment'),
    
    # User APIs
    path('api/user/stats/<str:user_email>/', views.user_stats, name='user_stats'),

    # Warning Handling
    path('.well-known/appspecific/com.chrome.devtools.json', lambda r: HttpResponse('{}', content_type='application/json')),
    path('favicon.ico', lambda r: HttpResponse('{}', content_type='application/json')),
    

    
]
