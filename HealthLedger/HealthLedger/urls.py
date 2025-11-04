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
    
    # MANAGEMENT SECTION - High Level
    path("", views.DASH, name="Dashboard"),                                        # Main management dashboard
    path('new_record/', views.CREATE, name='home'),                                # Create new patient record
    path('update_record/', views.UPDATE, name='update'),                           # Update existing record
    path('view_all/', views.VIEW_ALL, name='view_all'),                           # View all patient records
    path('print/<str:invoice_num>/', views.PRINT_INVOICE, name='print_invoice'),  # Print invoice page
    path('analytics/', views.ANALYTICAL_DASHBOARD, name='analytics_dashboard'),    # Analytics dashboard
    
    path('register/', views.REGISTER, name='register'),                            # Staff registration page
    path('login/', views.LOGIN, name='login'),                                     # Staff login page
    path('logout/', views.LOGOUT, name='logout'),                                  # Staff logout page
    path('logout/<str:status>/', views.LOGOUT_HARD, name='logout_hard'),          # Hard logout with status
    
    
    # USER SECTION - High Level
    path('login/patient/', views.user_login, name='user_login'),                   # Patient login page
    path('user/<str:user_email>/', views.user_dashboard, name='user_dashboard'),  # Patient dashboard
    path('user/<str:user_email>/invoices/', views.user_invoices, name='user_invoices'),  # Patient invoices page
    
    
    # COMMON APIS
    path('api/get_data_by_uid', views.get_data_by_uid, name='get_data_by_uid'),                      # Get patient data by UID
    path('api/get_data_by_invoice_id', views.get_data_by_invoice_id, name='get_data_by_invoice_id'),  # Get data by invoice number
    path('api/invoice/<str:invoice_num>/', views.detailed_invoice_view, name='detailed_invoice'),     # Get detailed invoice view
    path('api/records/', views.load_data, name='api_records'),                                        # Load paginated records with filters
    path('api/records/count/', views.records_count, name='api_records_count'),                        # Get total record count
    
    path('api/update_payment/', views.update_payment, name='update_payment'),                         # Update payment for invoice
    path('razorpay_payment/', views.razorpay_payment_window, name='razorpay_payment_window'),        # Razorpay payment window
    path('api/initiate_payment/', views.initiate_payment, name='initiate_payment'),                   # Initiate Razorpay payment
    path('api/verify_payment/', views.verify_payment, name='verify_payment'),                         # Verify Razorpay payment
    
    
    # MANAGEMENT APIS - API Level
    path('api/load_data/', views.load_data, name='load_data'),                                        # Load data for management dashboard
    path('api/recent-activity/', views.recent_activity, name='recent_activity'),                      # Get recent activity logs
    path('api/get_stats/', views.getstats, name='get_stats'),                                         # Get overall statistics
    
    path('api/add_new_data/', views.add_new_data_row, name='add_new_data'),                          # Add new patient record
    path('api/get_all_uids/', views.api_get_all_uids, name='api_get_all_uids'),                      # Get all patient UIDs
    path('api/generate_invoice_number/', views.api_generate_invoice_number, name='api_generate_invoice_number'),  # Generate new invoice number
    path('api/get_user_by_uid/', views.api_get_user_by_uid, name='api_get_user_by_uid'),             # Get user details by UID
    
    path('api/auth_stats/', views.api_auth_stats, name='api_auth_stats'),                            # Get authentication statistics
    path('api/generate_uid/', views.api_generate_uid, name='api_generate_uid'),                      # Generate new UID for patient
    path('api/register_user/', views.api_register_user, name='api_register_user'),                   # Register new user/patient
    path('api/registration_pdf/<str:uid>/', views.registration_pdf, name='registration_pdf'),        # Generate registration PDF
    
    path('api/financial_summary/', views.api_financial_summary, name='api_financial_summary'),       # Financial summary data
    path('api/patient_stats/', views.api_patient_stats, name='api_patient_stats'),                   # Patient statistics
    path('api/activity_trends/', views.api_activity_trends, name='api_activity_trends'),             # Activity trends over time
    path('api/payment_modes/', views.api_payment_modes, name='api_payment_modes'),                   # Payment mode distribution
    path('api/patients_list/', views.api_patients_list, name='api_patients_list'),                   # List of all patients
    path('api/ai_insights/', views.api_ai_insights, name='api_ai_insights'),                         # AI-generated insights
    path('api/generate_report/', views.api_generate_report, name='api_generate_report'),             # Generate PDF reports
    
    
    # USER APIS - API Level
    path('api/user/invoices/<str:user_email>/', views.api_user_invoices, name='api_user_invoices'),  # Get user invoices by email
    path('api/user/stats/<str:user_email>/', views.user_stats, name='user_stats'),                   # Get user statistics
    path('api/user/payment/<str:amount>/', views.user_payment, name='api_user_payment'),             # User payment endpoint (deprecated)
    
    
    # ========================================
    # UTILITY ROUTES
    # ========================================
    path('.well-known/appspecific/com.chrome.devtools.json', lambda r: HttpResponse('{}', content_type='application/json')),  # Chrome DevTools
    path('favicon.ico', lambda r: HttpResponse('{}', content_type='application/json')),              # Favicon handler
]
