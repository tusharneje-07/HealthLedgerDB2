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
    path('api/get_all_uids/', views.api_get_all_uids, name='api_get_all_uids'),
    path('api/generate_invoice_number/', views.api_generate_invoice_number, name='api_generate_invoice_number'),
    path('api/get_user_by_uid/', views.api_get_user_by_uid, name='api_get_user_by_uid'),
    path('api/auth_stats/', views.api_auth_stats, name='api_auth_stats'),
    # Registration
    path('register/', views.REGISTER, name='register'),
    path('api/generate_uid/', views.api_generate_uid, name='api_generate_uid'),
    path('api/register_user/', views.api_register_user, name='api_register_user'),
    path('api/registration_pdf/<str:uid>/', views.registration_pdf, name='registration_pdf'),
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
    
    # Analytics Dashboard
    path('analytics/', views.analytics_dashboard, name='analytics_dashboard'),
    path('api/financial_summary/', views.api_financial_summary, name='api_financial_summary'),
    path('api/patient_stats/', views.api_patient_stats, name='api_patient_stats'),
    path('api/activity_trends/', views.api_activity_trends, name='api_activity_trends'),
    path('api/payment_modes/', views.api_payment_modes, name='api_payment_modes'),
    path('api/patients_list/', views.api_patients_list, name='api_patients_list'),
    path('api/ai_insights/', views.api_ai_insights, name='api_ai_insights'),
    path('api/generate_report/', views.api_generate_report, name='api_generate_report'),

    # Warning Handling
    path('.well-known/appspecific/com.chrome.devtools.json', lambda r: HttpResponse('{}', content_type='application/json')),
    path('favicon.ico', lambda r: HttpResponse('{}', content_type='application/json')),
    

    
]
