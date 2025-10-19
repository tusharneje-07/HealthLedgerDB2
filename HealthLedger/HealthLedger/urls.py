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
    path('print/<str:invoice_num>/', views.PRINT_INVOICE, name='print_invoice'),
    path('logout/', views.LOGOUT, name='logout'),
    path('login/', views.LOGIN, name='login'),
    
    # Endpoint to let client check presence of HttpOnly auth cookie (server reads it)
    path('auth/cookie-info', views.auth_cookie_info, name='auth_cookie_info'),
    path('auth/cookie-info/', views.auth_cookie_info),
    
    # APIS
    path('api/get_data_by_uid', views.get_data_by_uid, name='get_data_by_uid'),
    path('api/get_data_by_invoice_id', views.get_data_by_invoice_id, name='get_data_by_invoice_id'),
    path('api/update_payment/', views.update_payment, name='update_payment'),
    path('api/load_data/', views.load_data, name='load_data'),
    # alias for records listing (supports pagination/search)
    path('api/records/', views.load_data, name='api_records'),
    path('api/records/count/', views.records_count, name='api_records_count'),
    path('api/recent-activity/', views.recent_activity, name='recent_activity'),
    path('api/get_stats/', views.getstats, name='get_stats'),
    path('api/add_new_data/', views.ADD_NEW_DATA, name='add_new_data'),
    path('api/invoice/<str:invoice_num>/', views.detailed_invoice_view, name='detailed_invoice'),
    
    # Warning Handling
    path('.well-known/appspecific/com.chrome.devtools.json', lambda r: HttpResponse('{}', content_type='application/json')),
    path('favicon.ico', lambda r: HttpResponse('{}', content_type='application/json')),
    
    
    # # WebAuthn / Passkey endpoints
    # path('webauthn/register/options', views.webauthn_register_options, name='webauthn_register_options'),
    # path('webauthn/register/complete', views.webauthn_register_complete, name='webauthn_register_complete'),
    # path('webauthn/authenticate/options', views.webauthn_authenticate_options, name='webauthn_authenticate_options'),
    # path('webauthn/authenticate/complete', views.webauthn_authenticate_complete, name='webauthn_authenticate_complete'),
    # # trailing slash variants (avoid 301/redirect POST issues)
    # path('webauthn/register/options/', views.webauthn_register_options),
    # path('webauthn/register/complete/', views.webauthn_register_complete),
    # path('webauthn/authenticate/options/', views.webauthn_authenticate_options),
    # path('webauthn/authenticate/complete/', views.webauthn_authenticate_complete),
    
]
