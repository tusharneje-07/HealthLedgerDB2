from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from .DB2 import DB2Query
from datetime import datetime, timedelta
from collections import defaultdict
from django.utils import timezone
import hashlib, base64
import json
import requests
import random
import re
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import razorpay
import os
from dotenv import load_dotenv
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.barcharts import VerticalBarChart
import resend

# Load environment variables
load_dotenv()

# Configure Resend API
resend.api_key = os.getenv('RESEND_API_KEY')

# In-memory OTP storage (in production, use Redis or database)
OTP_STORAGE = {}


# ===================================================== HIGH LEVEL VIEWS =====================================================
# ===================================================== MANAGEMENT VIEWS
def DASH(request):
    auth_token = request.COOKIES.get('auth_token')
    if auth_token and request.session.get(f'{auth_token}_is_authenticated'):
        return render(request, 'src/management/DASH.html')
    else:
        return redirect('/login')

def CREATE(request):
    return render(request, 'src/management/CREATE.html')

def UPDATE(request):
    return render(request, 'src/management/UPDATE.html')

def VIEW_ALL(request):
    query = f"""
        SELECT
            p.REC_NUMBER,
            p.UID,
            p.USERNAME,
            p.INNVOCE_NUM,
            p.DATE,
            p.AMOUNT,
            CASE
                WHEN COALESCE(il.TOTAL_PAID, 0) > 0 THEN il.TOTAL_PAID
                ELSE COALESCE(r.PAID_AMT, 0)
            END AS PAID_AMOUNT
        FROM patient_data p
        LEFT JOIN register r
            ON p.UID = r.UID
            AND p.INNVOCE_NUM = r.INNVOCE_NUM
        LEFT JOIN (
            SELECT INVOICE_NUMBER, COALESCE(SUM(PAID_AMOUNT_ON_DATE), 0) AS TOTAL_PAID
            FROM INVOICE_LOGS
            GROUP BY INVOICE_NUMBER
        ) il
            ON p.INNVOCE_NUM = il.INVOICE_NUMBER
        ORDER BY p.DATE DESC
    """

    success, invoices = DB2Query.runSelectQuery(query)

    if not success:
        return JsonResponse({"error": "Failed to load data"}, status=500)

    if not invoices:
        return render(request, 'src/management/VIEW_ALL.html', {"records": []})

    invoice_nums = [f"'{row['INNVOCE_NUM']}'" for row in invoices if row.get('INNVOCE_NUM') is not None]
    formatted_result = []

    logs_by_invoice = defaultdict(list)
    if invoice_nums:
        invoice_num_list = ", ".join(invoice_nums)
        log_query = f"""
            SELECT INVOICE_NUMBER, LOG_DATE, PAID_AMOUNT_ON_DATE, LOG_REMARK
            FROM INVOICE_LOGS
            WHERE INVOICE_NUMBER IN ({invoice_num_list})
            ORDER BY LOG_DATE DESC
        """
        log_success, log_result = DB2Query.runSelectQuery(log_query)
        if log_success and log_result:
            for log in log_result:
                if log.get("PAID_AMOUNT_ON_DATE") is not None:
                    logs_by_invoice[log["INVOICE_NUMBER"]].append({
                        "date": str(log["LOG_DATE"]),
                        "paid_amount_on_date": float(log["PAID_AMOUNT_ON_DATE"] or 0),
                        "log_remark": log.get("LOG_REMARK"),
                    })

    for row in invoices:
        amount = float(row.get("AMOUNT") or 0)
        invoice_num = row.get("INNVOCE_NUM")
        detailed_logs = logs_by_invoice.get(invoice_num, [])
        sum_from_logs = sum(l.get("paid_amount_on_date", 0.0) for l in detailed_logs)

        paid_amount = float(sum_from_logs) if sum_from_logs > 0 else float(row.get("PAID_AMOUNT") or 0.0)

        remaining = max(0, amount - paid_amount)
        remark = "Paid" if paid_amount >= amount else "Pending"

        formatted_result.append({
            "recNumber": row.get("REC_NUMBER"),
            "uid": row.get("UID"),
            "username": row.get("USERNAME"),
            "invoiceNum": invoice_num,
            "date": str(row.get("DATE")),
            "amount": amount,
            "paidAmount": paid_amount,
            "remainingAmount": remaining,
            "remark": remark,
            "detailed_logs": detailed_logs,
            "see_details": "/print/" + (invoice_num or ""),
        })

    return render(request, 'src/management/VIEW_ALL.html', {"records": formatted_result})

def PRINT_INVOICE(request, invoice_num):
    return render(request, 'src/management/PRINT_INVOICE.html', {"invoice_num": invoice_num})

def LOGIN(request):
    if request.method == 'GET':
        return render(request, 'src/management/LOGIN.html')

    username = request.POST.get('username') or request.POST.get('email')
    password = request.POST.get('password')
    user_type = request.POST.get('user_type') or 'S'  # Default to 'S' for staff
    
    if request.method == 'POST' and request.POST.get('has_token_key'):
        auth_token = request.COOKIES.get('auth_token')
        has_token_key = request.POST.get('has_token_key')
        key = request.session.get(has_token_key)
        if key and auth_token == key:
            request.session[f'{auth_token}_is_authenticated'] = True
            return redirect('/')
        else:
            return render(request, 'src/management/LOGIN.html', {'error':True, 'error_msg': 'Invalid authentication key'})
        

    query = f"SELECT UID, NAME, EMAIL, PASSWORD, FLAG FROM AUTHENTICATION WHERE (UID = '{username}' OR EMAIL = '{username}') AND FLAG = '{user_type[0].upper()}'"
    ok, res = DB2Query.runSelectQuery(query)
    if ok and res:
        user = res[0]
        stored_password = user.get('PASSWORD')
        if stored_password == password:
            try:
                email = (user.get('EMAIL') or user.get('UID') or '')
                auth_token = hashlib.sha256(email.encode()).hexdigest()

                request.session[f'{auth_token}'] = auth_token
                request.session[f'{auth_token}_user_uid'] = user.get('UID')
                request.session[f'{auth_token}_user_name'] = user.get('NAME')
                request.session[f'{auth_token}_user_email'] = user.get('EMAIL')
                request.session[f'{auth_token}_user_flag'] = user.get('FLAG')
                request.session[f'{auth_token}_is_authenticated'] = True

                a,b = DB2Query.runQuery("UPDATE AUTHENTICATION SET KEY = '{}' WHERE EMAIL = '{}'".format(auth_token, user.get('EMAIL')))
                
                response = redirect('/')
                response.set_cookie(
                    'auth_token',
                    auth_token,
                    max_age=3 * 60 * 60,   # 3 hours in seconds
                    httponly=False,
                    secure=request.is_secure(),
                    samesite='Lax'
                )
                response.set_cookie(
                    'auth_token_name',
                    user.get('EMAIL'),
                    max_age=3 * 60 * 60,   # 3 hours in seconds
                    httponly=False,
                    secure=request.is_secure(),
                    samesite='Lax'
                )
                response.set_cookie(
                    'user_type',
                    'S',
                    max_age=3 * 60 * 60,   # 3 hours in seconds
                    httponly=False,
                    secure=request.is_secure(),
                    samesite='Lax'
                )
                return response
                
            except Exception:
                pass
        else:
            return render(request, 'src/management/LOGIN.html', {'error':True, 'error_msg': 'Invalid username or password'})

def LOGOUT(request):
    auth_token = request.COOKIES.get('auth_token')
    if auth_token and request.session.get(f'{auth_token}_is_authenticated'):
        request.session[f'{auth_token}_is_authenticated'] = False
        
    return render(request, 'src/management/LOGOUT.html')

def LOGOUT_HARD(request, status):
    auth_token = request.COOKIES.get('auth_token')
    response = redirect('/login')
    if auth_token:
        response.delete_cookie('auth_token')
        response.delete_cookie('auth_token_name')
        response.delete_cookie('user_type')
        
    return response

def razorpay_payment_window(request):
    amount = request.GET.get('amount')
    invoice_num = request.GET.get('invoice_num')
    uid = request.GET.get('uid')
    total_amount = request.GET.get('total_amount')
    
    if not all([amount, invoice_num, uid, total_amount]):
        return HttpResponse("Missing required parameters", status=400)
    
    try:
        amount = float(amount)
        total_amount = float(total_amount)
    except ValueError:
        return HttpResponse("Invalid amount", status=400)
    
    try:
        amount_in_paise = int(amount * 100)
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        
        order_data = {
            'amount': amount_in_paise,
            'currency': 'INR',
            'payment_capture': 1,
            'notes': {
                'invoice_num': invoice_num,
                'uid': uid
            }
        }
        
        order = client.order.create(data=order_data)
        order_id = order['id']
        
        context = {
            'amount': amount,
            'invoice_num': invoice_num,
            'uid': uid,
            'total_amount': total_amount,
            'order_id': order_id,
            'razorpay_key': settings.RAZORPAY_KEY_ID,
            'amount_in_paise': amount_in_paise
        }
        
        return render(request, 'src/management/RAZORPAY_PAYMENT.html', context)
        
    except Exception as e:
        return HttpResponse(f"Error creating payment: {str(e)}", status=500)

def ANALYTICAL_DASHBOARD(request):
    auth_token = request.COOKIES.get('auth_token')
    if auth_token and request.session.get(f'{auth_token}_is_authenticated'):
        return render(request, 'src/management/ANALYTICS.html')
    else:
        return redirect('/login')

def REGISTER(request):
    return render(request, 'src/management/REGISTER.html')

# ===================================================== MANAGEMENT VIEWS

# ===================================================== USER VIEWS
def user_login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        if request.POST.get('has_token_key'):
            auth_token = request.COOKIES.get('auth_token')
            has_token_key = request.POST.get('has_token_key')
            key = request.session.get(has_token_key)
            print("Auth key login triggered.",has_token_key, key, auth_token)
            if key and auth_token == key:
                request.session[f'{auth_token}_is_authenticated'] = True
                
                email = request.COOKIES.get('auth_token_name').replace('"','')
                return redirect('/user/'+email+'/')
            else:
                return render(request, 'src/management/LOGIN.html', {'error': 'Invalid user authentication key'})
        
        query = f"SELECT UID, NAME, PASSWORD FROM AUTHENTICATION WHERE EMAIL = '{email}' AND FLAG = 'P'"
        ok, res = DB2Query.runSelectQuery(query)
        if ok and res:
            user = res[0]
            stored_password = user.get('PASSWORD')
            if stored_password == password:
                auth_token = hashlib.sha256(email.encode()).hexdigest()
                request.session[f'{auth_token}_user_uid'] = user.get('UID')
                request.session[f'{auth_token}_user_name'] = user.get('NAME')
                request.session[f'{auth_token}_is_authenticated'] = True
                request.session[f'{auth_token}'] = auth_token
                response = redirect('/user/'+email+'/')
                response.set_cookie(
                    'auth_token',
                    auth_token,
                    max_age=3 * 60 * 60,
                    httponly=False,
                    secure=request.is_secure(),
                    samesite='Lax'
                )
                response.set_cookie(
                    'auth_token_name',
                    email,
                    max_age=3 * 60 * 60,
                    httponly=False,
                    secure=request.is_secure(),
                    samesite='Lax'
                )
                response.set_cookie(
                    'user_type',
                    'P',
                    max_age=3 * 60 * 60,
                    httponly=False,
                    secure=request.is_secure(),
                    samesite='Lax'
                )
                return response

        return render(request, 'src/management/LOGIN.html', {'error': 'Invalid UID or password'})
    return render(request, 'src/user/DASH.html')

def user_dashboard(request, user_email):
    auth_token = request.COOKIES.get('auth_token')
    if auth_token and request.session.get(f'{auth_token}_is_authenticated'):
        return render(request, 'src/user/DASH.html', {'user_email_d': user_email, 'user_email': user_email})
    else:
        return redirect('/login/')
    
def user_invoices(request, user_email):
    auth_token = request.COOKIES.get('auth_token')
    if auth_token and request.session.get(f'{auth_token}_is_authenticated'):
        return render(request, 'src/user/INVOICES.html', {'user_email_d': user_email, 'user_email': user_email})
    else:
        return redirect('/login/')

# ===================================================== USER VIEWS
# ===================================================== HIGH LEVEL VIEWS =====================================================

# ===================================================== API VIEWS =====================================================
def get_data_by_uid(request):
    uid = request.GET.get('uid')
    if not uid:
        return JsonResponse({"error": "UID is required"}, status=400)

    query = f"""
        SELECT 
            p.REC_NUMBER,
            p.UID,
            p.USERNAME,
            p.INNVOCE_NUM,
            p.DATE,
            p.AMOUNT,
            COALESCE(r.PAID_AMT, 0) AS PAID_AMT
        FROM patient_data p
        LEFT JOIN register r
        ON p.UID = r.UID AND p.INNVOCE_NUM = r.INNVOCE_NUM
        WHERE p.UID = '{uid}'
        FETCH FIRST 1 ROW ONLY
    """

    success, result = DB2Query.runSelectQuery(query)
    if not success or not result:
        return JsonResponse([], safe=False)

    row = result[0]
    amount = float(row['AMOUNT'])
    paid_amount = float(row['PAID_AMT'])
    remark = "Paid" if paid_amount >= amount else "Pending"

    send_data = {
        "recNumber": row['REC_NUMBER'],
        "uid": row['UID'],
        "username": row['USERNAME'],
        "invoiceNum": row['INNVOCE_NUM'],
        "date": str(row['DATE']),
        "amount": amount,
        "paidAmount": paid_amount,
        "remainingAmount": max(0, amount - paid_amount),
        "remark": remark,
        "see_details" : "/invoice/"+row['INNVOCE_NUM']
    }

    return JsonResponse([send_data], safe=False)

def get_data_by_invoice_id(request):
    invoice_num = request.GET.get('invoice_num')
    if not invoice_num:
        return JsonResponse({"error": "Invoice number is required"}, status=400)

    invoice_query = f"""
        SELECT 
            p.REC_NUMBER,
            p.UID,
            p.USERNAME,
            p.INNVOCE_NUM,
            p.DATE,
            p.AMOUNT,
            COALESCE(SUM(il.PAID_AMOUNT_ON_DATE), 0) AS PAID_AMOUNT
        FROM patient_data p
        LEFT JOIN register r
            ON p.UID = r.UID AND p.INNVOCE_NUM = r.INNVOCE_NUM
        LEFT JOIN INVOICE_LOGS il
            ON p.INNVOCE_NUM = il.INVOICE_NUMBER
        WHERE p.INNVOCE_NUM = '{invoice_num}'
        GROUP BY 
            p.REC_NUMBER, p.UID, p.USERNAME, 
            p.INNVOCE_NUM, p.DATE, p.AMOUNT
        FETCH FIRST 1 ROW ONLY
    """
    success, result = DB2Query.runSelectQuery(invoice_query)
    if not success or not result:
        return JsonResponse([], safe=False)

    row = result[0]
    amount = float(row["AMOUNT"])
    paid_amount = float(row.get("PAID_AMOUNT", 0))
    remaining = max(0, amount - paid_amount)
    remark = "Paid" if paid_amount >= amount else "Pending"

    log_query = f"""
        SELECT LOG_DATE, PAID_AMOUNT_ON_DATE, LOG_REMARK
        FROM INVOICE_LOGS
        WHERE INVOICE_NUMBER = '{invoice_num}'
        ORDER BY LOG_DATE DESC
    """
    log_success, log_result = DB2Query.runSelectQuery(log_query)

    detailed_logs = []
    if log_success and log_result:
        for log in log_result:
            if log.get("PAID_AMOUNT_ON_DATE") is not None:
                detailed_logs.append({
                    "date": str(log["LOG_DATE"]),
                    "paid_amount_on_date": float(log["PAID_AMOUNT_ON_DATE"] or 0),
                    "log_remark": log.get("LOG_REMARK"),
                })

    send_data = {
        "recNumber": row["REC_NUMBER"],
        "uid": row["UID"],
        "username": row["USERNAME"],
        "invoiceNum": row["INNVOCE_NUM"],
        "date": str(row["DATE"]),
        "amount": amount,
        "paidAmount": paid_amount,
        "remainingAmount": remaining,
        "remark": remark,
        "detailed_logs": detailed_logs,
        "see_details": "/invoice/" + row["INNVOCE_NUM"],
    }

    return JsonResponse([send_data], safe=False)

def update_payment(request):
    uid = request.GET.get("uid")
    invoice_num = request.GET.get("invoice_num")
    paid_amount = request.GET.get("paid_amount")
    total_amount = request.GET.get("total_amount")
    by = request.GET.get("by", "mode:cash|id:null")

    if not uid or not invoice_num or not paid_amount:
        return JsonResponse(
            {"error": "uid, invoice_num, and paid_amount are required"}, status=400
        )

    try:
        paid_amount = float(paid_amount)
        total_amount = float(total_amount) if total_amount else 0.0
    except ValueError:
        return JsonResponse(
            {"error": "paid_amount and total_amount must be numeric"}, status=400
        )

    payment_mode = "CASH"
    payment_id = "null"
    
    if by:
        parts = by.split('|')
        for part in parts:
            if ':' in part:
                key, value = part.split(':', 1)
                if key.strip() == 'mode':
                    payment_mode = value.strip()
                elif key.strip() == 'id':
                    payment_id = value.strip()

    remaining_amount = max(0, total_amount - paid_amount)
    current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    update_query = (
        f"UPDATE register "
        f"SET PAID_AMT = {paid_amount} "
        f"WHERE UID = '{uid}' AND INNVOCE_NUM = '{invoice_num}'"
    )

    success, msg = DB2Query.runQuery(update_query)
    if not success:
        return JsonResponse({"error": f"Failed to update payment: {msg}"}, status=500)

    if payment_id == "null":
        payment_id = "N/A"
    log_desc = f"Payment done for {invoice_num}, ₹{paid_amount}/- Paid by {payment_mode.upper()} (Payment ID: {payment_id})"
    insert_activity_query = (
        "INSERT INTO activity (log_name, log_desc, log_date_time) "
        f"VALUES ('Payment Update', '{log_desc}', '{current_timestamp}')"
    )
    DB2Query.runQuery(insert_activity_query)

    
    log_remark = f"Payment updated of {invoice_num}, ₹{paid_amount}/- Paid via {payment_mode.upper()} (Payment ID: {payment_id})"
    insert_invoice_query = (
        "INSERT INTO INVOICE_LOGS "
        "(INVOICE_NUMBER, UID, LOG_DATE, AMOUNT, PAID_AMOUNT_ON_DATE, "
        "REMAINING_AMOUNT_ON_DATE, LOG_REMARK, PAYMENT_MODE,PAYMENT_ID) "
        f"VALUES ('{invoice_num}', '{uid}', '{current_timestamp}', "
        f"{total_amount}, {paid_amount}, {remaining_amount}, '{log_remark}','{payment_mode.upper()}','{payment_id}')"
    )
    DB2Query.runQuery(insert_invoice_query)

    return JsonResponse({"message": "Payment updated successfully"})

def recent_activity(request):
    if request.method == "GET":
        sql = "SELECT log_name, log_desc, log_date_time FROM activity ORDER BY log_date_time DESC FETCH FIRST 10 ROWS ONLY"
        success, result = DB2Query.runSelectQuery(sql)
        if success:
            data = []
            for row in result:
                data.append({
                    "log_name": row["LOG_NAME"],
                    "log_desc": row["LOG_DESC"],
                    "log_date_time": row["LOG_DATE_TIME"].strftime("%Y-%m-%d %H:%M:%S")
                })
            return JsonResponse({"activities": data})
        else:
            return JsonResponse({"error": result}, status=500)
        
def getstats(request):
    query = """
        SELECT
            COUNT(*) AS TOTAL_RECORDS,
            COALESCE(SUM(p.AMOUNT), 0) AS TOTAL_REVENUE,
            COALESCE(SUM(
                CASE
                    WHEN COALESCE(il.TOTAL_PAID, 0) >= p.AMOUNT THEN 0
                    ELSE p.AMOUNT - COALESCE(il.TOTAL_PAID, 0)
                END
            ), 0) AS TOTAL_PENDING_AMOUNT,
            COALESCE(SUM(
                CASE
                    WHEN COALESCE(il.TOTAL_PAID, 0) >= p.AMOUNT THEN 1
                    ELSE 0
                END
            ), 0) AS TOTAL_PAID_CUSTOMERS
        FROM patient_data p
        LEFT JOIN (
            SELECT INVOICE_NUMBER, COALESCE(SUM(PAID_AMOUNT_ON_DATE), 0) AS TOTAL_PAID
            FROM INVOICE_LOGS
            GROUP BY INVOICE_NUMBER
        ) il
        ON p.INNVOCE_NUM = il.INVOICE_NUMBER
    """

    success, result = DB2Query.runSelectQuery(query)
    if not success or not result:
        return JsonResponse({"error": "Failed to fetch stats"}, status=500)

    row = result[0]
    total_records = int(row.get("TOTAL_RECORDS") or 0)
    total_revenue = float(row.get("TOTAL_REVENUE") or 0.0)
    total_pending_amount = float(row.get("TOTAL_PENDING_AMOUNT") or 0.0)
    total_paid_customers = int(row.get("TOTAL_PAID_CUSTOMERS") or 0)

    stats = {
        "total_records": total_records,
        "total_revenue": total_revenue,
        "total_pending_amount": total_pending_amount,
        "total_paid_customers": total_paid_customers,
    }

    return JsonResponse(stats)

def add_new_data_row(request):
    if request.method == "GET":
        uid = request.GET.get("uid")
        username = request.GET.get("username")
        innvoce_num = request.GET.get("invoiceNum")
        date = request.GET.get("date")
        amount = request.GET.get("amount")

        if not uid or not username or not innvoce_num or not date or not amount:
            return JsonResponse({"error": "All fields are required"}, status=400)

        try:
            amount = float(amount)
        except ValueError:
            return JsonResponse({"error": "Amount must be a number"}, status=400)

        patient_data_sql = f"""
            INSERT INTO patient_data (uid, username, innvoce_num, date, amount)
            VALUES ('{uid}', '{username}', '{innvoce_num}', '{date}', {amount})
        """
        a, b = DB2Query.runQuery(patient_data_sql)
        if not a:
            return JsonResponse({"error": f"Failed to insert into patient_data: {b}"}, status=500)

        register_sql = f"""
            INSERT INTO register (uid, innvoce_num, paid_amt)
            VALUES ('{uid}', '{innvoce_num}', 0)
        """
        a, b = DB2Query.runQuery(register_sql)
        if not a:
            return JsonResponse({"error": f"Failed to insert into register: {b}"}, status=500)

        return JsonResponse({"status":True,"message": "Record added successfully"})
    else:
        return JsonResponse({"error": "Invalid request method"}, status=405)

def detailed_invoice_view(request, invoice_num):
    if not invoice_num:
        return JsonResponse({"error": "Invoice number is required"}, status=400)

    query = f"""
        SELECT 
            p.REC_NUMBER,
            p.UID,
            p.USERNAME,
            p.INNVOCE_NUM,
            p.DATE,
            p.AMOUNT,
            COALESCE(SUM(il.PAID_AMOUNT_ON_DATE), 0) AS TOTAL_PAID
        FROM patient_data p
        LEFT JOIN register r 
            ON p.UID = r.UID 
            AND p.INNVOCE_NUM = r.INNVOCE_NUM
        LEFT JOIN INVOICE_LOGS il
            ON p.INNVOCE_NUM = il.INVOICE_NUMBER
        WHERE p.INNVOCE_NUM = '{invoice_num}'
        GROUP BY 
            p.REC_NUMBER, p.UID, p.USERNAME, 
            p.INNVOCE_NUM, p.DATE, p.AMOUNT
        FETCH FIRST 1 ROW ONLY
    """

    success, result = DB2Query.runSelectQuery(query)
    if not success or not result:
        return JsonResponse({"error": "Invoice not found"}, status=404)

    row = result[0]
    amount = float(row["AMOUNT"])
    paid_amount = float(row.get("TOTAL_PAID", 0))

    log_query = f"""
        SELECT LOG_DATE, PAID_AMOUNT_ON_DATE, LOG_REMARK
        FROM INVOICE_LOGS
        WHERE INVOICE_NUMBER = '{invoice_num}'
        ORDER BY LOG_DATE DESC
    """
    log_success, log_result = DB2Query.runSelectQuery(log_query)

    amount_logs = []
    if log_success and log_result:
        amount_logs = [
            {
                "date": log["LOG_DATE"],
                "paid_amount_on_date": float(log["PAID_AMOUNT_ON_DATE"] or 0),
                "log_remark": log["LOG_REMARK"],
            }
            for log in log_result
            if log.get("PAID_AMOUNT_ON_DATE") is not None
        ]

    remark = "Paid" if paid_amount >= amount else "Pending"

    invoice_data = {
        "recNumber": row["REC_NUMBER"],
        "uid": row["UID"],
        "username": row["USERNAME"],
        "invoiceNum": row["INNVOCE_NUM"],
        "date": str(row["DATE"]),
        "amount": amount,
        "paidAmount": paid_amount,
        "remainingAmount": max(0, amount - paid_amount),
        "remark": remark,
        "detailed_logs": amount_logs,
    }

    return JsonResponse(invoice_data)

def load_data(request):
    try:
        size = int(request.GET.get("size", 50))
        offset = int(request.GET.get("offset", 0))
    except ValueError:
        return JsonResponse({"error": "size Sand offset must be numbers"}, status=400)

    search = (request.GET.get('search') or '').strip()
    date_from = (request.GET.get('date_from') or '').strip()
    date_to = (request.GET.get('date_to') or '').strip()
    status = (request.GET.get('status') or '').strip().lower()  # expected: 'paid' or 'pending' or ''

    if size <= 0 or size > 1000 or offset < 0:
        return JsonResponse({"error": "Invalid size/offset"}, status=400)

    where_clause = ""
    wheres = []
    if search:
        s = search.replace("'", "''")
        wheres.append(
            f"(LOWER(p.USERNAME) LIKE LOWER('%{s}%') "
            f"OR LOWER(p.UID) LIKE LOWER('%{s}%') "
            f"OR LOWER(p.INNVOCE_NUM) LIKE LOWER('%{s}%'))"
        )
    if date_from:
        df = date_from.replace("'", "''")
        wheres.append(f"p.DATE >= '{df}'")
    if date_to:
        dt = date_to.replace("'", "''")
        wheres.append(f"p.DATE <= '{dt}'")

    where_clause = ''
    if wheres:
        where_clause = 'WHERE ' + ' AND '.join(wheres)

    base_cte = f"""
        WITH InvoiceData AS (
            SELECT 
                p.REC_NUMBER, 
                p.UID, 
                p.USERNAME, 
                p.INNVOCE_NUM, 
                p.DATE, 
                p.AMOUNT,
                COALESCE(SUM(il.PAID_AMOUNT_ON_DATE), 0) AS PAID_AMOUNT
            FROM patient_data p
            LEFT JOIN INVOICE_LOGS il ON p.INNVOCE_NUM = il.INVOICE_NUMBER
            {where_clause}
            GROUP BY 
                p.REC_NUMBER, p.UID, p.USERNAME, 
                p.INNVOCE_NUM, p.DATE, p.AMOUNT
        )
    """
    
    status_filter = ""
    if status == 'paid':
        status_filter = "WHERE PAID_AMOUNT >= AMOUNT"
    elif status == 'pending':
        status_filter = "WHERE PAID_AMOUNT < AMOUNT"
    
    count_query = f"""
        {base_cte}
        SELECT COUNT(*) AS TOTAL
        FROM InvoiceData
        {status_filter}
    """
    
    invoice_query = f"""
        {base_cte}
        SELECT * FROM InvoiceData
        {status_filter}
        ORDER BY DATE DESC
        OFFSET {offset} ROWS
        FETCH FIRST {size} ROWS ONLY
    """

    parallel_queries = [count_query, invoice_query]
    success, results = DB2Query.runParallelQueries(parallel_queries, max_workers=10)
    
    if not success:
        return JsonResponse({"error": f"Failed to load data: {results}"}, status=500)

    total_count = 0
    invoices = []
    
    if len(results) >= 2:
        count_result = results[0]
        if count_result and len(count_result) > 0:
            total_count = int(count_result[0].get('TOTAL') or count_result[0].get('total') or 0)
        
        invoices = results[1] if results[1] else []
    else:
        return JsonResponse({"error": "Unexpected query results format"}, status=500)

    if not invoices:
        resp = JsonResponse([], safe=False)
        resp['X-Total-Count'] = str(total_count)
        return resp

    invoice_nums = [f"'{row['INNVOCE_NUM']}'" for row in invoices]
    invoice_num_list = ", ".join(invoice_nums)
    
    log_query = f"""
        SELECT INVOICE_NUMBER, LOG_DATE, PAID_AMOUNT_ON_DATE, LOG_REMARK
        FROM INVOICE_LOGS
        WHERE INVOICE_NUMBER IN ({invoice_num_list})
        ORDER BY INVOICE_NUMBER, LOG_DATE DESC
    """
    
    logs_by_invoice = defaultdict(list)
    log_success, log_results = DB2Query.runSelectQuery(log_query)
    
    if log_success and log_results:
        for log in log_results:
            if log.get("PAID_AMOUNT_ON_DATE") is not None:
                logs_by_invoice[log["INVOICE_NUMBER"]].append({
                    "date": str(log["LOG_DATE"]),
                    "paid_amount_on_date": float(log["PAID_AMOUNT_ON_DATE"] or 0),
                    "log_remark": log.get("LOG_REMARK"),
                })

    formatted_result = []
    for row in invoices:
        amount = float(row["AMOUNT"])
        paid_amount = float(row.get("PAID_AMOUNT", 0))
        remaining = max(0, amount - paid_amount)
        remark = "Paid" if paid_amount >= amount else "Pending"
        invoice_num = row["INNVOCE_NUM"]

        detailed_logs = logs_by_invoice.get(invoice_num, [])

        formatted_result.append({
            "recNumber": row["REC_NUMBER"],
            "uid": row["UID"],
            "username": row["USERNAME"],
            "invoiceNum": invoice_num,
            "date": str(row["DATE"]),
            "amount": amount,
            "paidAmount": paid_amount,
            "remainingAmount": remaining,
            "remark": remark,
            "detailed_logs": detailed_logs,
            "details": {
                "recNumber": row["REC_NUMBER"],
                "uid": row["UID"],
                "username": row["USERNAME"],
                "invoiceNum": invoice_num,
                "date": str(row["DATE"]),
                "amount": amount,
                "paidAmount": paid_amount,
                "remainingAmount": remaining,
                "remark": remark,
            },
        })

    resp = JsonResponse(formatted_result, safe=False)
    resp['X-Total-Count'] = str(total_count)
    
    return resp

def records_count(request):
    search = (request.GET.get('search') or '').strip()
    date_from = (request.GET.get('date_from') or '').strip()
    date_to = (request.GET.get('date_to') or '').strip()

    wheres = []
    if search:
        s = search.replace("'", "''")
        wheres.append(
            f"(LOWER(p.USERNAME) LIKE LOWER('%{s}%') OR LOWER(p.UID) LIKE LOWER('%{s}%') OR LOWER(p.INNVOCE_NUM) LIKE LOWER('%{s}%'))"
        )
    if date_from:
        df = date_from.replace("'", "''")
        wheres.append(f"p.DATE >= '{df}'")
    if date_to:
        dt = date_to.replace("'", "''")
        wheres.append(f"p.DATE <= '{dt}'")

    where_clause = ''
    if wheres:
        where_clause = 'WHERE ' + ' AND '.join(wheres)

    try:
        count_query = f"""
            SELECT COUNT(*) AS TOTAL
            FROM (
                SELECT p.INNVOCE_NUM
                FROM patient_data p
                {where_clause}
                GROUP BY p.INNVOCE_NUM
            ) AS SUB
        """
        ok, res = DB2Query.runSelectQuery(count_query)
        if ok and res:
            total = int(res[0].get('TOTAL') or res[0].get('total') or 0)
            return JsonResponse({'total': total})
        return JsonResponse({'total': 0})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def user_stats(request, user_email):
    auth_token = request.COOKIES.get('auth_token')
    if not auth_token or not request.session.get(f'{auth_token}_is_authenticated'):
        return JsonResponse({"error": "Unauthorized"}, status=401)

    if not user_email:
        return JsonResponse({"error": "User email not found in session"}, status=400)

    email_s = user_email.replace("'", "''")

    uid_q = f"SELECT UID FROM AUTHENTICATION WHERE EMAIL = '{email_s}' FETCH FIRST 1 ROW ONLY"
    ok, uid_res = DB2Query.runSelectQuery(uid_q)
    if not ok:
        return JsonResponse({"error": "Failed to resolve user"}, status=500)
    if not uid_res:
        return JsonResponse({"error": "User not found"}, status=404)

    uid = uid_res[0].get("UID")
    if not uid:
        return JsonResponse({"error": "User UID not found"}, status=404)

    now = timezone.now()
    this_month = now.month
    this_year = now.year
    if this_month == 1:
        last_month = 12
        last_month_year = this_year - 1
    else:
        last_month = this_month - 1
        last_month_year = this_year

    summary_query = f"""
        WITH il AS (
            SELECT INVOICE_NUMBER, COALESCE(SUM(PAID_AMOUNT_ON_DATE), 0) AS TOTAL_PAID
            FROM INVOICE_LOGS
            GROUP BY INVOICE_NUMBER
        )
        SELECT
            COUNT(*) AS TOTAL_INVOICES,
            COALESCE(SUM(p.AMOUNT), 0) AS TOTAL_AMOUNT,
            COALESCE(SUM(
                CASE WHEN COALESCE(il.TOTAL_PAID,0) < p.AMOUNT THEN p.AMOUNT - COALESCE(il.TOTAL_PAID,0) ELSE 0 END
            ), 0) AS PENDING_DUES,
            COALESCE(SUM(CASE WHEN COALESCE(il.TOTAL_PAID,0) = 0 THEN 1 ELSE 0 END), 0) AS UNPAID_COUNT,
            COALESCE(SUM(CASE WHEN COALESCE(il.TOTAL_PAID,0) >= p.AMOUNT THEN COALESCE(p.AMOUNT,0) ELSE COALESCE(il.TOTAL_PAID,0) END), 0) AS PAID_AMOUNT,
            COALESCE(SUM(CASE WHEN COALESCE(il.TOTAL_PAID,0) >= p.AMOUNT THEN 1 ELSE 0 END), 0) AS PAID_COUNT,
            COALESCE(SUM(CASE WHEN COALESCE(il.TOTAL_PAID,0) > 0 AND COALESCE(il.TOTAL_PAID,0) < p.AMOUNT THEN 1 ELSE 0 END), 0) AS PENDING_COUNT
        FROM patient_data p
        LEFT JOIN il ON p.INNVOCE_NUM = il.INVOICE_NUMBER
        WHERE p.UID = '{uid}'
    """
    ok, summary_res = DB2Query.runSelectQuery(summary_query)
    if not ok or not summary_res:
        return JsonResponse({"error": "Failed to fetch summary"}, status=500)
    srow = summary_res[0]

    summary = {
        "total_invoices": int(srow.get("TOTAL_INVOICES") or 0),
        "total_amount": float(srow.get("TOTAL_AMOUNT") or 0.0),
        "pending_dues": float(srow.get("PENDING_DUES") or 0.0),
        "unpaid_count": int(srow.get("UNPAID_COUNT") or 0),
        "paid_amount": float(srow.get("PAID_AMOUNT") or 0.0),
        "paid_count": int(srow.get("PAID_COUNT") or 0),
        "pending_count": int(srow.get("PENDING_COUNT") or 0),
    }

    payments_q = f"""
        WITH user_invoices AS (
            SELECT INNVOCE_NUM FROM patient_data WHERE UID = '{uid}'
        )
        SELECT
            COALESCE(SUM(CASE WHEN MONTH(LOG_DATE) = {this_month} AND YEAR(LOG_DATE) = {this_year} THEN PAID_AMOUNT_ON_DATE ELSE 0 END), 0) AS THIS_MONTH,
            COALESCE(SUM(CASE WHEN MONTH(LOG_DATE) = {last_month} AND YEAR(LOG_DATE) = {last_month_year} THEN PAID_AMOUNT_ON_DATE ELSE 0 END), 0) AS LAST_MONTH
        FROM INVOICE_LOGS il
        JOIN user_invoices ui ON ui.INNVOCE_NUM = il.INVOICE_NUMBER
    """
    ok, pay_res = DB2Query.runSelectQuery(payments_q)
    if not ok or not pay_res:
        return JsonResponse({"error": "Failed to fetch payment summary"}, status=500)
    prow = pay_res[0]

    payment_summary = {
        "this_month": float(prow.get("THIS_MONTH") or 0.0),
        "last_month": float(prow.get("LAST_MONTH") or 0.0)
    }

    recent_q = f"""
        WITH user_invoices AS (
            SELECT INNVOCE_NUM, AMOUNT FROM patient_data WHERE UID = '{uid}'
        ),
        total_paid AS (
            SELECT INVOICE_NUMBER, COALESCE(SUM(PAID_AMOUNT_ON_DATE),0) AS TOTAL_PAID
            FROM INVOICE_LOGS
            WHERE INVOICE_NUMBER IN (SELECT INNVOCE_NUM FROM user_invoices)
            GROUP BY INVOICE_NUMBER
        )
        SELECT il.INVOICE_NUMBER, il.LOG_DATE, il.PAID_AMOUNT_ON_DATE, COALESCE(tp.TOTAL_PAID,0) AS TOTAL_PAID, ui.AMOUNT
        FROM INVOICE_LOGS il
        JOIN user_invoices ui ON ui.INNVOCE_NUM = il.INVOICE_NUMBER
        LEFT JOIN total_paid tp ON tp.INVOICE_NUMBER = il.INVOICE_NUMBER
        ORDER BY il.LOG_DATE DESC
        FETCH FIRST 5 ROWS ONLY
    """
    ok, recent_res = DB2Query.runSelectQuery(recent_q)
    recent_transactions = []
    if ok and recent_res:
        for r in recent_res:
            invoice_number = r.get("INVOICE_NUMBER")
            amount = float(r.get("PAID_AMOUNT_ON_DATE") or 0.0)
            log_date = r.get("LOG_DATE")
            date_s = str(log_date)[:10] if log_date is not None else None
            total_paid = float(r.get("TOTAL_PAID") or 0.0)
            invoice_amount = float(r.get("AMOUNT") or 0.0)

            status = "paid" if total_paid >= invoice_amount else "pending"

            recent_transactions.append({
                "invoice_number": invoice_number,
                "amount": amount,
                "date": date_s,
                "status": status
            })

    result = {
        "summary": summary,
        "payment_summary": payment_summary,
        "recent_transactions": recent_transactions
    }

    return JsonResponse(result)

@csrf_exempt
def initiate_payment(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST method allowed"}, status=405)
    
    try:
        data = json.loads(request.body)
        amount = float(data.get('amount', 0))
        invoice_num = data.get('invoice_num', '')
        uid = data.get('uid', '')
        
        if not amount or not invoice_num or not uid:
            return JsonResponse({"error": "Missing required fields"}, status=400)
        
        if amount <= 0:
            return JsonResponse({"error": "Invalid amount"}, status=400)
        
        amount_in_paise = int(amount * 100)
        
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        
        order_data = {
            'amount': amount_in_paise,
            'currency': 'INR',
            'payment_capture': 1,
            'notes': {
                'invoice_num': invoice_num,
                'uid': uid
            }
        }
        
        order = client.order.create(data=order_data)
        order_id = order['id']
        
        return JsonResponse({
            "success": True,
            "order_id": order_id,
            "amount": amount_in_paise,
            "currency": "INR",
            "key": settings.RAZORPAY_KEY_ID,
            "invoice_num": invoice_num,
            "uid": uid
        })
        
    except razorpay.errors.BadRequestError as e:
        return JsonResponse({"error": f"Razorpay error: {str(e)}"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
def verify_payment(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST method allowed"}, status=405)
    
    try:
        razorpay_payment_id = request.POST.get('razorpay_payment_id')
        razorpay_order_id = request.POST.get('razorpay_order_id')
        razorpay_signature = request.POST.get('razorpay_signature')
        
        invoice_num = request.POST.get('invoice_num')
        uid = request.POST.get('uid')
        amount = request.POST.get('amount')
        total_amount = request.POST.get('total_amount')
        
        if not all([razorpay_payment_id, razorpay_order_id, razorpay_signature, invoice_num, uid, amount, total_amount]):
            return JsonResponse({"error": "Missing required fields"}, status=400)
        
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        
        params_dict = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        }
        
        try:
            client.utility.verify_payment_signature(params_dict)
        except razorpay.errors.SignatureVerificationError:
            return JsonResponse({"error": "Payment signature verification failed"}, status=400)
        
        paid_amount = float(amount)
        total_amt = float(total_amount)
        
        uid_s = uid.replace("'", "''")
        invoice_s = invoice_num.replace("'", "''")
        payment_id_s = razorpay_payment_id.replace("'", "''")
        
        remaining_amount = max(0, total_amt - paid_amount)
        current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        update_query = (
            f"UPDATE register "
            f"SET PAID_AMT = {paid_amount} "
            f"WHERE UID = '{uid_s}' AND INNVOCE_NUM = '{invoice_s}'"
        )
        
        success, msg = DB2Query.runQuery(update_query)
        if not success:
            return JsonResponse({"error": "Failed to update payment in database"}, status=500)
        
        log_desc = f"Payment update for {invoice_num}, ₹{paid_amount}/- Paid via Razorpay (Payment ID: {razorpay_payment_id})."
        insert_activity_query = (
            "INSERT INTO activity (log_name, log_desc, log_date_time) "
            f"VALUES ('Razorpay Payment', '{log_desc}', '{current_timestamp}')"
        )
        DB2Query.runQuery(insert_activity_query)
        log_remark = f"Payment updated of {invoice_num}, ₹{paid_amount}/- Paid via RAZ (Payment ID: {razorpay_payment_id})"
        insert_invoice_query = (
            "INSERT INTO INVOICE_LOGS "
            "(INVOICE_NUMBER, UID, LOG_DATE, AMOUNT, PAID_AMOUNT_ON_DATE, "
            "REMAINING_AMOUNT_ON_DATE, LOG_REMARK, PAYMENT_MODE, PAYMENT_ID) "
            f"VALUES ('{invoice_s}', '{uid_s}', '{current_timestamp}', "
            f"{total_amt}, {paid_amount}, {remaining_amount}, '{log_remark}', 'RAZ', '{payment_id_s}')"
        )
        DB2Query.runQuery(insert_invoice_query)
        
        return JsonResponse({
            "success": True,
            "message": "Payment verified and updated successfully",
            "payment_id": razorpay_payment_id,
            "invoice_num": invoice_num,
            "amount_paid": paid_amount
        })
        
    except razorpay.errors.SignatureVerificationError:
        return JsonResponse({"error": "Invalid payment signature"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

def user_payment(request, amount):
    return JsonResponse({
        "error": "This endpoint is deprecated. Use /api/initiate_payment/ and /api/verify_payment/ instead."
    }, status=501)

def api_user_invoices(request, user_email):
    try:
        decoded_email = base64.b64decode(user_email).decode('utf-8')
    except Exception:
        return JsonResponse({'error': 'Invalid encoded email'}, status=400)

    email_s = decoded_email.replace("'", "''")

    uid_q = f"SELECT UID FROM AUTHENTICATION WHERE EMAIL = '{email_s}' FETCH FIRST 1 ROW ONLY"
    ok, uid_res = DB2Query.runSelectQuery(uid_q)
    if not ok or not uid_res:
        return JsonResponse([], safe=False)

    uid = uid_res[0].get('UID')
    if not uid:
        return JsonResponse([], safe=False)

    invoice_query = f"""
        SELECT 
            p.REC_NUMBER,
            p.UID,
            p.USERNAME,
            p.INNVOCE_NUM,
            p.DATE,
            p.AMOUNT,
            COALESCE(SUM(il.PAID_AMOUNT_ON_DATE), 0) AS PAID_AMOUNT
        FROM patient_data p
        LEFT JOIN INVOICE_LOGS il ON p.INNVOCE_NUM = il.INVOICE_NUMBER
        WHERE p.UID = '{uid}'
        GROUP BY p.REC_NUMBER, p.UID, p.USERNAME, p.INNVOCE_NUM, p.DATE, p.AMOUNT
        ORDER BY p.DATE DESC
    """

    success, invoices = DB2Query.runSelectQuery(invoice_query)
    if not success or not invoices:
        return JsonResponse([], safe=False)

    formatted = []
    for row in invoices:
        amount = float(row.get('AMOUNT') or 0)
        paid_amount = float(row.get('PAID_AMOUNT') or 0)
        remaining = max(0, amount - paid_amount)
        remark = 'Paid' if paid_amount >= amount else 'Pending'

        formatted.append({
            'recNumber': row.get('REC_NUMBER'),
            'uid': row.get('UID'),
            'username': row.get('USERNAME'),
            'invoiceNum': row.get('INNVOCE_NUM'),
            'date': str(row.get('DATE')),
            'amount': amount,
            'paidAmount': paid_amount,
            'remainingAmount': remaining,
            'remark': remark,
        })

    return JsonResponse(formatted, safe=False)

def api_financial_summary(request):
    try:
        total_revenue_query = """
            SELECT COALESCE(SUM(AMOUNT), 0) AS TOTAL_REVENUE
            FROM PATIENT_DATA
        """
        
        total_collected_query = """
            SELECT COALESCE(SUM(PAID_AMOUNT_ON_DATE), 0) AS TOTAL_COLLECTED
            FROM INVOICE_LOGS
        """
        
        outstanding_query = """
            SELECT COALESCE(SUM(p.AMOUNT) - SUM(COALESCE(il.TOTAL_PAID, 0)), 0) AS OUTSTANDING
            FROM PATIENT_DATA p
            LEFT JOIN (
                SELECT INVOICE_NUMBER, SUM(PAID_AMOUNT_ON_DATE) AS TOTAL_PAID
                FROM INVOICE_LOGS
                GROUP BY INVOICE_NUMBER
            ) il ON p.INNVOCE_NUM = il.INVOICE_NUMBER
        """
        
        monthly_query = """
            SELECT 
                SUBSTR(CHAR(LOG_DATE), 1, 7) AS MONTH,
                COALESCE(SUM(PAID_AMOUNT_ON_DATE), 0) AS REVENUE
            FROM INVOICE_LOGS
            WHERE LOG_DATE >= CURRENT_DATE - 12 MONTHS
            GROUP BY SUBSTR(CHAR(LOG_DATE), 1, 7)
            ORDER BY MONTH ASC
        """
        
        success1, rev_result = DB2Query.runSelectQuery(total_revenue_query)
        success2, col_result = DB2Query.runSelectQuery(total_collected_query)
        success3, out_result = DB2Query.runSelectQuery(outstanding_query)
        success4, mon_result = DB2Query.runSelectQuery(monthly_query)
        
        if not (success1 and success2 and success3 and success4):
            return JsonResponse({"error": "Failed to fetch financial data"}, status=500)
        
        total_revenue = float(rev_result[0].get('TOTAL_REVENUE', 0)) if rev_result else 0
        total_collected = float(col_result[0].get('TOTAL_COLLECTED', 0)) if col_result else 0
        outstanding = float(out_result[0].get('OUTSTANDING', 0)) if out_result else 0
        monthly = [{'month': row['MONTH'], 'revenue': float(row['REVENUE'])} for row in mon_result] if mon_result else []
        
        return JsonResponse({
            'total_revenue': total_revenue,
            'total_collected': total_collected,
            'outstanding': outstanding,
            'monthly': monthly
        })
        
    except Exception as e:
        return JsonResponse({"error": f"Error loading financial summary: {str(e)}"}, status=500)

def api_patient_stats(request):
    try:
        total_patients_query = """
            SELECT COUNT(DISTINCT UID) AS TOTAL_PATIENTS
            FROM PATIENT_DATA
        """
        
        avg_spending_query = """
            SELECT COALESCE(AVG(AMOUNT), 0) AS AVG_SPENDING
            FROM PATIENT_DATA
        """
        
        repeat_patients_query = """
            SELECT COUNT(*) AS REPEAT_PATIENTS
            FROM (
                SELECT UID
                FROM PATIENT_DATA
                GROUP BY UID
                HAVING COUNT(*) > 1
            ) AS repeat
        """
        
        top_patients_query = """
            SELECT 
                p.UID,
                p.USERNAME AS NAME,
                COALESCE(SUM(il.PAID_AMOUNT_ON_DATE), 0) AS TOTAL_PAID
            FROM PATIENT_DATA p
            LEFT JOIN INVOICE_LOGS il ON p.INNVOCE_NUM = il.INVOICE_NUMBER
            GROUP BY p.UID, p.USERNAME
            ORDER BY TOTAL_PAID DESC
            FETCH FIRST 10 ROWS ONLY
        """
        
        success1, pat_result = DB2Query.runSelectQuery(total_patients_query)
        success2, avg_result = DB2Query.runSelectQuery(avg_spending_query)
        success3, rep_result = DB2Query.runSelectQuery(repeat_patients_query)
        success4, top_result = DB2Query.runSelectQuery(top_patients_query)
        
        if not (success1 and success2 and success3 and success4):
            return JsonResponse({"error": "Failed to fetch patient stats"}, status=500)
        
        total_patients = int(pat_result[0].get('TOTAL_PATIENTS', 0)) if pat_result else 0
        avg_spending = float(avg_result[0].get('AVG_SPENDING', 0)) if avg_result else 0
        repeat_patients = int(rep_result[0].get('REPEAT_PATIENTS', 0)) if rep_result else 0
        top_patients = [
            {
                'uid': row['UID'],
                'name': row.get('NAME', 'Unknown'),
                'total_paid': float(row.get('TOTAL_PAID', 0))
            }
            for row in top_result
        ] if top_result else []
        
        return JsonResponse({
            'total_patients': total_patients,
            'avg_spending': avg_spending,
            'repeat_patients': repeat_patients,
            'top_patients': top_patients
        })
        
    except Exception as e:
        return JsonResponse({"error": f"Error loading patient stats: {str(e)}"}, status=500)

def api_activity_trends(request):
    try:
        invoice_volume_query = """
            SELECT 
                SUBSTR(CHAR(DATE), 1, 7) AS MONTH,
                COUNT(*) AS COUNT
            FROM PATIENT_DATA
            WHERE DATE >= CURRENT_DATE - 12 MONTHS
            GROUP BY SUBSTR(CHAR(DATE), 1, 7)
            ORDER BY MONTH ASC
        """
        
        recent_logs_query = """
            SELECT LOG_NAME, LOG_DESC, LOG_DATE_TIME
            FROM ACTIVITY
            ORDER BY LOG_DATE_TIME DESC
            FETCH FIRST 10 ROWS ONLY
        """
        
        success1, vol_result = DB2Query.runSelectQuery(invoice_volume_query)
        success2, log_result = DB2Query.runSelectQuery(recent_logs_query)
        
        if not (success1 and success2):
            return JsonResponse({"error": "Failed to fetch activity trends"}, status=500)
        
        invoice_volume = [{'month': row['MONTH'], 'count': int(row['COUNT'])} for row in vol_result] if vol_result else []
        recent_logs = [
            {
                'log_name': row['LOG_NAME'],
                'log_desc': row['LOG_DESC'],
                'log_date_time': str(row['LOG_DATE_TIME'])
            }
            for row in log_result
        ] if log_result else []
        
        return JsonResponse({
            'invoice_volume': invoice_volume,
            'recent_logs': recent_logs,
            'daily_activity': []
        })
        
    except Exception as e:
        return JsonResponse({"error": f"Error loading activity trends: {str(e)}"}, status=500)

def api_payment_modes(request):
    try:
        query = """
            SELECT 
                COALESCE(PAYMENT_MODE, 'UNKNOWN') AS MODE,
                COUNT(*) AS COUNT,
                COALESCE(SUM(PAID_AMOUNT_ON_DATE), 0) AS AMOUNT
            FROM INVOICE_LOGS
            WHERE PAYMENT_MODE IS NOT NULL
            GROUP BY PAYMENT_MODE
            ORDER BY AMOUNT DESC
        """
        
        success, result = DB2Query.runSelectQuery(query)
        
        if not success or not result:
            return JsonResponse({
                'modes': [],
                'counts': [],
                'amounts': []
            })
        
        modes = [row['MODE'] for row in result]
        counts = [int(row['COUNT']) for row in result]
        amounts = [float(row['AMOUNT']) for row in result]
        
        return JsonResponse({
            'modes': modes,
            'counts': counts,
            'amounts': amounts
        })
        
    except Exception as e:
        return JsonResponse({"error": f"Error loading payment modes: {str(e)}"}, status=500)

def api_patients_list(request):
    try:
        query = """
            SELECT 
                p.REC_NUMBER,
                p.UID,
                p.USERNAME,
                p.INNVOCE_NUM,
                p.DATE,
                p.AMOUNT,
                COALESCE(SUM(il.PAID_AMOUNT_ON_DATE), 0) AS PAID_AMOUNT
            FROM PATIENT_DATA p
            LEFT JOIN INVOICE_LOGS il ON p.INNVOCE_NUM = il.INVOICE_NUMBER
            GROUP BY p.REC_NUMBER, p.UID, p.USERNAME, p.INNVOCE_NUM, p.DATE, p.AMOUNT
            ORDER BY p.DATE DESC
        """
        
        success, result = DB2Query.runSelectQuery(query)
        
        if not success or not result:
            return JsonResponse([], safe=False)
        
        patients_list = []
        for row in result:
            amount = float(row.get('AMOUNT', 0))
            paid_amount = float(row.get('PAID_AMOUNT', 0))
            remaining = max(0, amount - paid_amount)
            remark = "Paid" if paid_amount >= amount else "Pending"
            
            patients_list.append({
                'recNumber': row.get('REC_NUMBER'),
                'uid': row.get('UID'),
                'username': row.get('USERNAME'),
                'invoiceNum': row.get('INNVOCE_NUM'),
                'date': str(row.get('DATE')),
                'amount': amount,
                'paidAmount': paid_amount,
                'remainingAmount': remaining,
                'remark': remark
            })
        
        return JsonResponse(patients_list, safe=False)
        
    except Exception as e:
        return JsonResponse({"error": f"Error loading patients list: {str(e)}"}, status=500)

@csrf_exempt
def api_ai_insights(request):
    try:
        groq_api_key = os.getenv('GROQ_API_KEY')
        groq_model = os.getenv('GROQ_MODEL', 'llama-3.1-8b-instant')
        
        if not groq_api_key:
            return JsonResponse({
                "insights_text": "AI insights unavailable: API key not configured.",
                "highlights": ["Contact administrator to configure GROQ_API_KEY"],
                "confidence_score": 0.0
            })
        
        try:
            body = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            body = {}
        
        total_revenue_query = """
            SELECT COALESCE(SUM(AMOUNT), 0) AS TOTAL_REVENUE
            FROM PATIENT_DATA
        """
        
        total_collected_query = """
            SELECT COALESCE(SUM(PAID_AMOUNT_ON_DATE), 0) AS TOTAL_COLLECTED
            FROM INVOICE_LOGS
        """
        
        outstanding_query = """
            SELECT COALESCE(SUM(p.AMOUNT) - SUM(COALESCE(il.TOTAL_PAID, 0)), 0) AS TOTAL_OUTSTANDING
            FROM PATIENT_DATA p
            LEFT JOIN (
                SELECT INVOICE_NUMBER, SUM(PAID_AMOUNT_ON_DATE) AS TOTAL_PAID
                FROM INVOICE_LOGS
                GROUP BY INVOICE_NUMBER
            ) il ON p.INNVOCE_NUM = il.INVOICE_NUMBER
        """
        
        invoice_count_query = """
            SELECT COUNT(DISTINCT INNVOCE_NUM) AS TOTAL_INVOICES
            FROM PATIENT_DATA
        """
        
        avg_payment_query = """
            SELECT COALESCE(AVG(PAID_AMOUNT_ON_DATE), 0) AS AVG_PAYMENT
            FROM INVOICE_LOGS
        """
        
        monthly_query = """
            SELECT 
                SUBSTR(CHAR(LOG_DATE), 1, 7) AS MONTH,
                COALESCE(SUM(PAID_AMOUNT_ON_DATE), 0) AS REVENUE,
                COUNT(DISTINCT INVOICE_NUMBER) AS INVOICE_COUNT
            FROM INVOICE_LOGS
            WHERE LOG_DATE >= CURRENT_DATE - 6 MONTHS
            GROUP BY SUBSTR(CHAR(LOG_DATE), 1, 7)
            ORDER BY MONTH DESC
            FETCH FIRST 6 ROWS ONLY
        """
        
        payment_modes_query = """
            SELECT 
                COALESCE(PAYMENT_MODE, 'UNKNOWN') AS MODE,
                COUNT(*) AS COUNT,
                COALESCE(SUM(PAID_AMOUNT_ON_DATE), 0) AS AMOUNT
            FROM INVOICE_LOGS
            WHERE PAYMENT_MODE IS NOT NULL
            GROUP BY PAYMENT_MODE
            ORDER BY AMOUNT DESC
            FETCH FIRST 5 ROWS ONLY
        """
        
        top_patients_query = """
            SELECT 
                p.UID,
                p.USERNAME,
                COALESCE(SUM(il.PAID_AMOUNT_ON_DATE), 0) AS TOTAL_PAID
            FROM PATIENT_DATA p
            LEFT JOIN INVOICE_LOGS il ON p.INNVOCE_NUM = il.INVOICE_NUMBER
            GROUP BY p.UID, p.USERNAME
            ORDER BY TOTAL_PAID DESC
            FETCH FIRST 10 ROWS ONLY
        """
        
        patient_stats_query = """
            SELECT 
                COUNT(DISTINCT UID) AS TOTAL_PATIENTS,
                COALESCE(AVG(AMOUNT), 0) AS AVG_INVOICE_AMOUNT
            FROM PATIENT_DATA
        """
        
        queries = [
            total_revenue_query,
            total_collected_query,
            outstanding_query,
            invoice_count_query,
            avg_payment_query,
            monthly_query,
            payment_modes_query,
            top_patients_query,
            patient_stats_query
        ]
        
        success, results = DB2Query.runParallelQueries(queries, max_workers=9)
        
        if not success:
            return JsonResponse({
                "insights_text": "Unable to generate insights: data collection failed.",
                "highlights": [],
                "confidence_score": 0.0
            })
        
        total_revenue = results[0][0]['TOTAL_REVENUE'] if results[0] else 0
        total_collected = results[1][0]['TOTAL_COLLECTED'] if len(results) > 1 and results[1] else 0
        total_outstanding = results[2][0]['TOTAL_OUTSTANDING'] if len(results) > 2 and results[2] else 0
        total_invoices = results[3][0]['TOTAL_INVOICES'] if len(results) > 3 and results[3] else 0
        avg_payment = results[4][0]['AVG_PAYMENT'] if len(results) > 4 and results[4] else 0
        
        monthly_data = results[5] if len(results) > 5 else []
        payment_modes = results[6] if len(results) > 6 else []
        top_patients = results[7] if len(results) > 7 else []
        patient_stats = results[8][0] if len(results) > 8 and results[8] else {}
        
        context = {
            "timeframe": "Last 6 months",
            "currency": "INR",
            "financial_summary": {
                "total_revenue": float(total_revenue),
                "total_collected": float(total_collected),
                "total_outstanding": float(total_outstanding),
                "total_invoices": int(total_invoices),
                "avg_payment": float(avg_payment)
            },
            "monthly_trends": [
                {
                    "month": row['MONTH'],
                    "revenue": float(row['REVENUE']),
                    "invoice_count": int(row['INVOICE_COUNT'])
                }
                for row in monthly_data
            ],
            "payment_modes": [
                {
                    "mode": row['MODE'],
                    "count": int(row['COUNT']),
                    "amount": float(row['AMOUNT'])
                }
                for row in payment_modes
            ],
            "top_patients": [
                {
                    "uid": row['UID'],
                    "total_paid": float(row['TOTAL_PAID'])
                }
                for row in top_patients[:10]  # Limit to top 10
            ],
            "patient_stats": {
                "total_patients": int(patient_stats.get('TOTAL_PATIENTS', 0)),
                "avg_invoice_amount": float(patient_stats.get('AVG_INVOICE_AMOUNT', 0))
            }
        }
        
        prompt = f"""You are a financial analyst for a hospital billing system called HealthLedger.

Analyze the following financial and operational data and provide a concise summary with key insights:

**Financial Summary:**
- Total Revenue: ₹{context['financial_summary']['total_revenue']:,.2f}
- Total Collected: ₹{context['financial_summary']['total_collected']:,.2f}
- Outstanding Balance: ₹{context['financial_summary']['total_outstanding']:,.2f}
- Total Invoices: {context['financial_summary']['total_invoices']}
- Average Payment: ₹{context['financial_summary']['avg_payment']:,.2f}

**Monthly Revenue Trend (Last 6 Months):**
{json.dumps(context['monthly_trends'], indent=2)}

**Payment Mode Distribution:**
{json.dumps(context['payment_modes'], indent=2)}

**Patient Statistics:**
- Total Patients: {context['patient_stats']['total_patients']}
- Average Invoice Amount: ₹{context['patient_stats']['avg_invoice_amount']:,.2f}

**Top 10 Paying Patients (anonymized UIDs):**
{json.dumps(context['top_patients'][:10], indent=2)}

**Instructions:**
1. Provide a concise 3-4 sentence summary of the overall financial health.
2. Identify 2-3 key trends or anomalies (e.g., revenue growth/decline, payment mode preferences, outstanding balance concerns).
3. Suggest 2-3 prioritized actions to improve revenue collection or operational efficiency.
4. Keep your response professional and data-driven.
5. Do not include patient names or identifiable information.

Format your response as plain text with clear sections."""

        headers = {
            'Authorization': f'Bearer {groq_api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': groq_model,
            'messages': [
                {
                    'role': 'system',
                    'content': 'You are a financial analyst for a hospital billing system. Provide concise, actionable insights based on data.'
                },
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            'temperature': 0.3,  # Low temperature for deterministic output
            'max_tokens': 800
        }
        
        try:
            response = requests.post(
                'https://api.groq.com/openai/v1/chat/completions',
                headers=headers,
                json=payload,
                timeout=30
            )
            
            response.raise_for_status()
            groq_response = response.json()
            
            insights_text = groq_response['choices'][0]['message']['content']
            
            highlights = []
            lines = insights_text.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('- ') or line.startswith('• '):
                    highlights.append(line[2:])
                elif line.startswith(tuple(str(i) + '.' for i in range(1, 10))):
                    highlights.append(line.split('.', 1)[1].strip())
            
            highlights = highlights[:5]
            
            confidence_score = 0.7  # Base confidence
            if len(monthly_data) >= 6:
                confidence_score += 0.1
            if len(payment_modes) >= 3:
                confidence_score += 0.1
            if float(total_revenue) > 0:
                confidence_score += 0.1
            
            confidence_score = min(confidence_score, 1.0)
            
            response_data = {
                'insights_text': insights_text,
                'highlights': highlights,
                'confidence_score': confidence_score,
                'references': {
                    'total_invoices': context['financial_summary']['total_invoices'],
                    'monthly_trend_months': len(monthly_data),
                    'payment_modes_analyzed': len(payment_modes)
                }
            }
            
            auth_token = request.COOKIES.get('auth_token')
            if auth_token and request.session.get(f'{auth_token}_user_type') == 'S':
                response_data['raw_model_response'] = groq_response
            
            return JsonResponse(response_data)
            
        except requests.exceptions.RequestException as e:
            return JsonResponse({
                "insights_text": f"AI insights temporarily unavailable. Based on available data: Total revenue is ₹{context['financial_summary']['total_revenue']:,.2f} with ₹{context['financial_summary']['total_outstanding']:,.2f} outstanding. System serving {context['patient_stats']['total_patients']} patients with {context['financial_summary']['total_invoices']} invoices.",
                "highlights": [
                    f"Total Revenue: ₹{context['financial_summary']['total_revenue']:,.2f}",
                    f"Outstanding Balance: ₹{context['financial_summary']['total_outstanding']:,.2f}",
                    f"Active Patients: {context['patient_stats']['total_patients']}"
                ],
                "confidence_score": 0.5,
                "error": f"Groq API error: {str(e)}"
            })
            
    except Exception as e:
        return JsonResponse({
            "insights_text": "Error generating insights. Please try again later.",
            "highlights": [],
            "confidence_score": 0.0,
            "error": str(e)
        }, status=500)

@csrf_exempt
def api_generate_report(request):
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    auth_token = request.COOKIES.get('auth_token')
    if not auth_token or not request.session.get(f'{auth_token}_is_authenticated'):
        return JsonResponse({"error": "Unauthorized"}, status=401)
    
    try:
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        
        sections = body.get('sections', [])
        orientation = body.get('orientation', 'portrait')
        
        if not sections:
            return JsonResponse({"error": "No sections selected"}, status=400)
        
        report_data = {
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'orientation': orientation,
            'sections': {}
        }
        
        if 'kpi-section' in sections:
            total_revenue_query = """
                SELECT COALESCE(SUM(AMOUNT), 0) AS TOTAL_REVENUE
                FROM PATIENT_DATA
            """
            
            total_collected_query = """
                SELECT COALESCE(SUM(PAID_AMOUNT_ON_DATE), 0) AS TOTAL_COLLECTED
                FROM INVOICE_LOGS
            """            
            outstanding_query = """
                SELECT COALESCE(SUM(p.AMOUNT) - SUM(COALESCE(il.TOTAL_PAID, 0)), 0) AS OUTSTANDING
                FROM PATIENT_DATA p
                LEFT JOIN (
                    SELECT INVOICE_NUMBER, SUM(PAID_AMOUNT_ON_DATE) AS TOTAL_PAID
                    FROM INVOICE_LOGS
                    GROUP BY INVOICE_NUMBER
                ) il ON p.INNVOCE_NUM = il.INVOICE_NUMBER
            """
            
            patient_count_query = """
                SELECT COUNT(DISTINCT UID) AS TOTAL_PATIENTS
                FROM PATIENT_DATA
            """
            
            success1, revenue_result = DB2Query.runSelectQuery(total_revenue_query)
            success2, collected_result = DB2Query.runSelectQuery(total_collected_query)
            success3, outstanding_result = DB2Query.runSelectQuery(outstanding_query)
            success4, patient_result = DB2Query.runSelectQuery(patient_count_query)
            
            if success1 and revenue_result and success2 and collected_result and success3 and outstanding_result and success4 and patient_result:
                report_data['sections']['kpi'] = {
                    'total_revenue': float(revenue_result[0].get('TOTAL_REVENUE', 0)),
                    'total_collected': float(collected_result[0].get('TOTAL_COLLECTED', 0)),
                    'outstanding': float(outstanding_result[0].get('OUTSTANDING', 0)),
                    'total_patients': int(patient_result[0].get('TOTAL_PATIENTS', 0))
                }
        
        if 'revenue-trend-section' in sections:
            query = """
                SELECT 
                    SUBSTR(CHAR(LOG_DATE), 1, 7) AS MONTH,
                    COALESCE(SUM(PAID_AMOUNT_ON_DATE), 0) AS REVENUE
                FROM INVOICE_LOGS
                WHERE LOG_DATE >= CURRENT_DATE - 12 MONTHS
                GROUP BY SUBSTR(CHAR(LOG_DATE), 1, 7)
                ORDER BY MONTH ASC
            """
            success, result = DB2Query.runSelectQuery(query)
            if success and result:
                report_data['sections']['revenue_trend'] = [
                    {'month': row['MONTH'], 'revenue': float(row['REVENUE'])}
                    for row in result
                ]
        
        if 'payment-modes-section' in sections:
            query = """
                SELECT 
                    UPPER(COALESCE(PAYMENT_MODE, 'UNKNOWN')) AS MODE,
                    COUNT(*) AS COUNT,
                    COALESCE(SUM(PAID_AMOUNT_ON_DATE), 0) AS AMOUNT
                FROM INVOICE_LOGS
                WHERE PAYMENT_MODE IS NOT NULL
                GROUP BY UPPER(PAYMENT_MODE)
                ORDER BY AMOUNT DESC
            """
            success, result = DB2Query.runSelectQuery(query)
            if success and result:
                report_data['sections']['payment_modes'] = [
                    {'mode': row['MODE'], 'count': int(row['COUNT']), 'amount': float(row['AMOUNT'])}
                    for row in result
                ]
        
        if 'top-patients-section' in sections:
            query = """
                SELECT 
                    p.UID,
                    p.USERNAME,
                    COALESCE(SUM(il.PAID_AMOUNT_ON_DATE), 0) AS TOTAL_PAID
                FROM PATIENT_DATA p
                LEFT JOIN INVOICE_LOGS il ON p.INNVOCE_NUM = il.INVOICE_NUMBER
                GROUP BY p.UID, p.USERNAME
                ORDER BY TOTAL_PAID DESC
                FETCH FIRST 10 ROWS ONLY
            """
            success, result = DB2Query.runSelectQuery(query)
            if success and result:
                report_data['sections']['top_patients'] = [
                    {'uid': row['UID'], 'name': row['USERNAME'], 'total_paid': float(row['TOTAL_PAID'])}
                    for row in result
                ]
        
        if 'invoice-volume-section' in sections:
            query = """
                SELECT 
                    SUBSTR(CHAR(DATE), 1, 7) AS MONTH,
                    COUNT(*) AS COUNT
                FROM PATIENT_DATA
                WHERE DATE >= CURRENT_DATE - 12 MONTHS
                GROUP BY SUBSTR(CHAR(DATE), 1, 7)
                ORDER BY MONTH ASC
            """
            success, result = DB2Query.runSelectQuery(query)
            if success and result:
                report_data['sections']['invoice_volume'] = [
                    {'month': row['MONTH'], 'count': int(row['COUNT'])}
                    for row in result
                ]
        
        if 'activity-logs-section' in sections:
            query = """
                SELECT 
                    LOG_DATE_TIME,
                    LOG_NAME,
                    LOG_DESC
                FROM ACTIVITY
                ORDER BY LOG_DATE_TIME DESC
                FETCH FIRST 20 ROWS ONLY
            """
            success, result = DB2Query.runSelectQuery(query)
            if success and result:
                report_data['sections']['activity_logs'] = [
                    {
                        'log_date_time': str(row['LOG_DATE_TIME']),
                        'log_name': row['LOG_NAME'],
                        'log_desc': row['LOG_DESC']
                    }
                    for row in result
                ]
            else:
                print(f"DEBUG: Failed to fetch activity logs - success={success}, result={result}")  # Debug log
        
        if 'patients-list-section' in sections:
            query = """
                SELECT 
                    p.UID,
                    p.USERNAME,
                    p.INNVOCE_NUM,
                    p.DATE,
                    p.AMOUNT,
                    COALESCE(il.TOTAL_PAID, 0) AS PAID_AMOUNT
                FROM PATIENT_DATA p
                LEFT JOIN (
                    SELECT INVOICE_NUMBER, SUM(PAID_AMOUNT_ON_DATE) AS TOTAL_PAID
                    FROM INVOICE_LOGS
                    GROUP BY INVOICE_NUMBER
                ) il ON p.INNVOCE_NUM = il.INVOICE_NUMBER
                ORDER BY p.DATE DESC
            """
            success, result = DB2Query.runSelectQuery(query)
            if success and result:
                report_data['sections']['patients_list'] = [
                    {
                        'uid': row['UID'],
                        'username': row['USERNAME'],
                        'invoice_num': row['INNVOCE_NUM'],
                        'date': str(row['DATE']),
                        'amount': float(row['AMOUNT']),
                        'paid_amount': float(row['PAID_AMOUNT']),
                        'remaining_amount': float(row['AMOUNT']) - float(row['PAID_AMOUNT']),
                        'remark': 'Paid' if float(row['AMOUNT']) <= float(row['PAID_AMOUNT']) else 'Pending'
                    }
                    for row in result
                ]
            else:
                print(f"DEBUG: Failed to fetch patients - success={success}, result={result}")  # Debug log
        
        try:
            pdf_bytes = generate_reportlab_pdf(report_data, sections, orientation)
            
            if len(pdf_bytes) == 0:
                raise Exception("Generated PDF is empty")
            
            if not pdf_bytes.startswith(b'%PDF'):
                raise Exception("Generated file is not a valid PDF")
            
            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="HealthLedger_Report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf"'
            response['Content-Length'] = len(pdf_bytes)
            
            return response
            
        except Exception as pdf_error:
            import traceback
            error_details = traceback.format_exc()
            print(f"PDF Generation Error: {str(pdf_error)}")
            print(f"Traceback:\n{error_details}")
            
            return JsonResponse({
                "error": f"PDF generation failed: {str(pdf_error)}",
                "details": error_details
            }, status=500)
            
    except Exception as e:
        import traceback
        print(f"Report Generation Error: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            "error": f"Error generating report: {str(e)}"
        }, status=500)

def generate_reportlab_pdf(report_data, sections, orientation):
    buffer = BytesIO()

    pagesize = landscape(A4) if orientation == 'landscape' else A4
    page_width = pagesize[0]
    page_height = pagesize[1]

    doc = SimpleDocTemplate(
        buffer,
        pagesize=pagesize,
        rightMargin=0.5*inch,
        leftMargin=0.5*inch,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch
    )

    usable_width = page_width - 1*inch  # Total width minus margins

    story = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.white,
        spaceAfter=6,
        alignment=TA_CENTER,
        fontName='Times-Bold'
    )
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#e0e7ff'),
        alignment=TA_CENTER,
        spaceAfter=8,
        fontName='Times-Roman'
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#3b82f6'),
        spaceAfter=6,
        spaceBefore=8,
        fontName='Times-Bold'
    )
    normal_style = ParagraphStyle(
        'NormalText',
        parent=styles['Normal'],
        fontName='Times-Roman',
        fontSize=10,
        leading=12
    )
    small_style = ParagraphStyle(
        'SmallText',
        parent=styles['Normal'],
        fontName='Times-Roman',
        fontSize=8,
        leading=10
    )

    header_data = [[Paragraph("HealthLedger Analytics Report", title_style)],
                    [Paragraph(f"Generated: {report_data['generated_at']}", subtitle_style)]]
    header_table = Table(header_data, colWidths=[usable_width])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#3b82f6')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 12),
    ]))

    story.append(header_table)
    story.append(Spacer(1, 0.15*inch))

    if 'kpi-section' in sections and 'kpi' in report_data['sections']:
        kpi = report_data['sections']['kpi']
        story.append(Paragraph("Key Performance Indicators", heading_style))

        col_width = usable_width / 4
        kpi_cards = [
            ['Total Revenue', 'Collected Payments', 'Outstanding Balance', 'Total Patients'],
            [f"Rs. {kpi['total_revenue']:,.0f}", f"Rs. {kpi['total_collected']:,.0f}",
             f"Rs. {kpi['outstanding']:,.0f}", str(kpi['total_patients'])]
        ]

        kpi_table = Table(kpi_cards, colWidths=[col_width]*4)
        kpi_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#3b82f6')),
            ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#10b981')),
            ('BACKGROUND', (2, 0), (2, 0), colors.HexColor('#f59e0b')),
            ('BACKGROUND', (3, 0), (3, 0), colors.HexColor('#8b5cf6')),
            ('TEXTCOLOR', (0, 0), (3, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (3, 0), 'Times-Bold'),
            ('FONTSIZE', (0, 0), (3, 0), 10),
            ('ALIGN', (0, 0), (3, 0), 'CENTER'),
            ('TOPPADDING', (0, 0), (3, 0), 6),
            ('BOTTOMPADDING', (0, 0), (3, 0), 6),

            ('BACKGROUND', (0, 1), (0, 1), colors.HexColor('#dbeafe')),
            ('BACKGROUND', (1, 1), (1, 1), colors.HexColor('#d1fae5')),
            ('BACKGROUND', (2, 1), (2, 1), colors.HexColor('#fef3c7')),
            ('BACKGROUND', (3, 1), (3, 1), colors.HexColor('#ede9fe')),
            ('TEXTCOLOR', (0, 1), (3, 1), colors.HexColor('#1e40af')),
            ('FONTNAME', (0, 1), (3, 1), 'Times-Bold'),
            ('FONTSIZE', (0, 1), (3, 1), 14),
            ('ALIGN', (0, 1), (3, 1), 'CENTER'),
            ('TOPPADDING', (0, 1), (3, 1), 8),
            ('BOTTOMPADDING', (0, 1), (3, 1), 8),

            ('GRID', (0, 0), (-1, -1), 1.5, colors.white),
        ]))

        story.append(kpi_table)
        story.append(Spacer(1, 0.15*inch))

    if 'revenue-trend-section' in sections and 'revenue_trend' in report_data['sections']:
        story.append(Paragraph("Monthly Revenue Trend", heading_style))

        trend_items = report_data['sections']['revenue_trend']
        if trend_items:
            drawing = Drawing(usable_width * 0.45, 150)
            bc = VerticalBarChart()
            bc.x = 30
            bc.y = 20
            bc.height = 110
            bc.width = usable_width * 0.4
            bc.data = [[item['revenue'] for item in trend_items]]
            bc.categoryAxis.categoryNames = [item['month'] for item in trend_items]
            bc.categoryAxis.labels.angle = 45
            bc.categoryAxis.labels.fontSize = 7
            bc.categoryAxis.labels.fontName = 'Times-Roman'
            bc.valueAxis.valueMin = 0
            bc.valueAxis.labels.fontName = 'Times-Roman'
            bc.valueAxis.labels.fontSize = 7
            bc.bars[0].fillColor = colors.HexColor('#3b82f6')
            bc.barWidth = 12

            drawing.add(bc)
            story.append(drawing)

            trend_data = [['Month', 'Revenue']]
            for item in trend_items:
                trend_data.append([item['month'], f"Rs. {item['revenue']:,.0f}"])

            col_width = usable_width / 2
            trend_table = Table(trend_data, colWidths=[col_width, col_width])
            trend_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
                ('FONTNAME', (0, 1), (-1, -1), 'Times-Roman'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))

            story.append(trend_table)
        story.append(Spacer(1, 0.15*inch))

    if 'payment-modes-section' in sections and 'payment_modes' in report_data['sections']:
        story.append(Paragraph("Payment Mode Distribution", heading_style))

        payment_items = report_data['sections']['payment_modes']

        if payment_items:
            drawing = Drawing(usable_width * 0.4, 140)
            pc = Pie()
            pc.x = 60
            pc.y = 20
            pc.width = 100
            pc.height = 100
            pc.data = [item['amount'] for item in payment_items]
            pc.labels = [item['mode'] for item in payment_items]
            pc.slices.strokeWidth = 0.5
            pc.slices.fontName = 'Times-Roman'
            pc.slices.fontSize = 8

            chart_colors = [
                colors.HexColor('#3b82f6'),
                colors.HexColor('#10b981'),
                colors.HexColor('#f59e0b'),
                colors.HexColor('#8b5cf6'),
                colors.HexColor('#ec4899'),
                colors.HexColor('#14b8a6'),
            ]
            for i, item in enumerate(payment_items):
                pc.slices[i].fillColor = chart_colors[i % len(chart_colors)]

            drawing.add(pc)
            story.append(drawing)

            payment_data = [['Mode', 'Count', 'Amount']]
            for item in payment_items:
                payment_data.append([
                    item['mode'],
                    str(item['count']),
                    f"Rs. {item['amount']:,.0f}"
                ])

            col_width = usable_width / 3
            payment_table = Table(payment_data, colWidths=[col_width]*3)
            payment_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
                ('FONTNAME', (0, 1), (-1, -1), 'Times-Roman'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))

            story.append(payment_table)
        story.append(Spacer(1, 0.15*inch))

    if 'top-patients-section' in sections and 'top_patients' in report_data['sections']:
        story.append(Paragraph("Top 10 Paying Patients", heading_style))

        top_patients_items = report_data['sections']['top_patients']

        patients_data = [['UID', 'Name', 'Total Paid']]
        for item in top_patients_items:
            patients_data.append([
                item['uid'],
                item['name'][:25],
                f"Rs. {item['total_paid']:,.0f}"
            ])

        col_width = usable_width / 3
        patients_table = Table(patients_data, colWidths=[col_width, col_width, col_width])
        patients_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Times-Roman'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))

        story.append(patients_table)
        story.append(Spacer(1, 0.15*inch))

    if 'invoice-volume-section' in sections and 'invoice_volume' in report_data['sections']:
        story.append(Paragraph("Invoice Volume Trend", heading_style))

        volume_items = report_data['sections']['invoice_volume']

        volume_data = [['Month', 'Invoice Count']]
        for item in volume_items:
            volume_data.append([item['month'], str(item['count'])])

        col_width = usable_width / 2
        volume_table = Table(volume_data, colWidths=[col_width, col_width])
        volume_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Times-Roman'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))

        story.append(volume_table)
        story.append(Spacer(1, 0.15*inch))

    if 'activity-logs-section' in sections and 'activity_logs' in report_data['sections']:
        story.append(Paragraph("Recent System Activity", heading_style))

        activity_data = [['Date/Time', 'Activity', 'Description']]
        for item in report_data['sections']['activity_logs']:
            log_name = str(item['log_name']).replace('₹', 'Rs.').replace('✓', 'OK').replace('✗', 'X')
            log_desc = str(item['log_desc']).replace('₹', 'Rs.').replace('✓', 'OK').replace('✗', 'X')

            activity_data.append([
                item['log_date_time'][:16],
                log_name[:30],
                log_desc[:60]
            ])

        activity_table = Table(activity_data, colWidths=[usable_width*0.2, usable_width*0.25, usable_width*0.55])
        activity_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Times-Roman'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))

        story.append(activity_table)
        story.append(Spacer(1, 0.15*inch))

    if 'patients-list-section' in sections and 'patients_list' in report_data['sections']:
        story.append(Paragraph("All Patients List", heading_style))

        list_data = [['UID', 'Name', 'Invoice', 'Date', 'Amount', 'Paid', 'Status']]
        patients_to_show = report_data['sections']['patients_list']

        for item in patients_to_show:
            list_data.append([
                item['uid'][:12],
                item['username'][:20],
                item['invoice_num'][:12],
                item['date'][:10],
                f"Rs. {item['amount']:,.0f}",
                f"Rs. {item['paid_amount']:,.0f}",
                item['remark'][:8]
            ])

        if orientation == 'landscape':
            col_widths = [usable_width*0.12, usable_width*0.2, usable_width*0.15,
                         usable_width*0.13, usable_width*0.15, usable_width*0.15, usable_width*0.1]
        else:
            col_widths = [usable_width*0.12, usable_width*0.2, usable_width*0.15,
                         usable_width*0.13, usable_width*0.13, usable_width*0.13, usable_width*0.14]

        list_table = Table(list_data, colWidths=col_widths)
        list_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Times-Roman'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))

        story.append(list_table)
        story.append(Spacer(1, 0.1*inch))

    if True:
        story.append(Paragraph("AI Insights", heading_style))
        ai_paragraphs_added = False
        try:
            api_url = "http://127.0.0.1:8000/api/ai_insights/"
            resp = requests.get(api_url)
            if resp.ok:
                data = resp.json()
                insights_text = data.get('insights_text', '')
                highlights = data.get('highlights', [])
                confidence = data.get('confidence_score', 0)
                references = data.get('references', {})
                
                insights_text = insights_text.replace('₹', 'Rs.').replace('✓', 'OK').replace('✗', 'X').replace('**', '')
                # Ensure highlights is a list of cleaned strings (the API returns a list)
                if isinstance(highlights, list):
                    highlights = [
                        str(h).replace('₹', 'Rs.').replace('✓', 'OK').replace('✗', 'X').replace('**', '')
                        for h in highlights
                    ]
                else:
                    highlights = [str(highlights).replace('₹', 'Rs.').replace('✓', 'OK').replace('✗', 'X').replace('**', '')]

                if insights_text:
                    for part in insights_text.split('\n\n'):
                        part_safe = part.replace('\n', '<br/>')
                        story.append(Paragraph(part_safe, normal_style))
                        story.append(Spacer(1, 0.08*inch))
                    ai_paragraphs_added = True

                if highlights:
                    safe_lines = []
                    for h in highlights:
                        s = str(h).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', ' ')
                        if len(s) > 280:
                            s = s[:277] + '...'
                        safe_lines.append('• ' + s)
                    highlights_text = '<br/>'.join(safe_lines)
                    story.append(Paragraph(highlights_text, normal_style))
                    story.append(Spacer(1, 0.08*inch))
                    ai_paragraphs_added = True

                ref_data = [
                    ['Confidence', 'Total Invoices', 'Months Analyzed', 'Payment Modes']
                ]
                ref_data.append([
                    f"{confidence:.2f}",
                    str(references.get('total_invoices', '-')),
                    str(references.get('monthly_trend_months', '-')),
                    str(references.get('payment_modes_analyzed', '-'))
                ])
                ref_table = Table(ref_data, colWidths=[usable_width*0.2, usable_width*0.266, usable_width*0.266, usable_width*0.266])
                ref_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#374151')),
                    ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
                    ('FONTNAME', (0, 1), (-1, -1), 'Times-Roman'),
                    ('FONTSIZE', (0, 0), (-1, 0), 9),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
                ]))
                story.append(ref_table)
                story.append(Spacer(1, 0.15*inch))
            else:
                story.append(Paragraph("AI Insights: API returned an error.", normal_style))
                story.append(Spacer(1, 0.08*inch))
        except Exception:
            story.append(Paragraph("AI Insights: Failed to fetch insights from the AI service.", normal_style))
            story.append(Spacer(1, 0.08*inch))

        if not ai_paragraphs_added:
            story.append(Paragraph("AI Insights are unavailable.", small_style))
            story.append(Spacer(1, 0.08*inch))

    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey,
        alignment=TA_CENTER,
        fontName='Times-Italic'
    )
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph(
        "HealthLedger Analytics System | Confidential",
        footer_style
    ))

    doc.build(story)

    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes

def api_get_all_uids(request):
    query = """
        SELECT DISTINCT UID, NAME, EMAIL 
        FROM AUTHENTICATION 
        WHERE FLAG = 'P'
        ORDER BY UID
    """
    success, result = DB2Query.runSelectQuery(query)
    
    if not success or not result:
        return JsonResponse([], safe=False)
    
    users = [
        {
            "uid": row.get("UID"),
            "name": row.get("NAME"),
            "email": row.get("EMAIL")
        }
        for row in result
    ]
    
    return JsonResponse(users, safe=False)

def api_generate_invoice_number(request):
    query = """
        SELECT INNVOCE_NUM 
        FROM patient_data 
        ORDER BY REC_NUMBER DESC 
        FETCH FIRST 1 ROW ONLY
    """
    success, result = DB2Query.runSelectQuery(query)
    
    if not success or not result:
        new_invoice_num = "INV00000001"
    else:
        last_invoice = result[0].get("INNVOCE_NUM", "INV00000000")
        try:
            num_part = int(last_invoice.replace("INV", ""))
            new_num = num_part + 1
            new_invoice_num = f"INV{new_num:08d}"
        except:
            new_invoice_num = "INV00000001"
    
    return JsonResponse({"invoice_number": new_invoice_num})

def api_get_user_by_uid(request):
    uid = request.GET.get('uid')
    if not uid:
        return JsonResponse({"error": "UID is required"}, status=400)
    
    query = f"""
        SELECT UID, NAME, EMAIL 
        FROM AUTHENTICATION 
        WHERE UID = '{uid}' AND FLAG = 'P'
        FETCH FIRST 1 ROW ONLY
    """
    success, result = DB2Query.runSelectQuery(query)
    
    if not success or not result:
        return JsonResponse({"error": "User not found"}, status=404)
    
    user_data = {
        "uid": result[0].get("UID"),
        "name": result[0].get("NAME"),
        "email": result[0].get("EMAIL")
    }
    
    return JsonResponse(user_data)

def api_auth_stats(request):
    try:
        ok, res = DB2Query.runSelectQuery("SELECT EMAIL FROM AUTHENTICATION WHERE EMAIL IS NOT NULL")
        if not ok:
            return JsonResponse({'error': 'Failed to query authentication table'}, status=500)

        total = 0
        domain_counts = {}
        common = ['gmail.com', 'yahoo.com', 'outlook.com', 'healthledger.com', 'email.com', 'hotmail.com']
        others = 0
        if res:
            for row in res:
                email = (row.get('EMAIL') or '').strip().lower()
                if not email:
                    continue
                total += 1
                parts = email.split('@')
                domain = parts[1] if len(parts) > 1 else 'unknown'
                domain_counts[domain] = domain_counts.get(domain, 0) + 1

        resp = {'total_users': total, 'domains': {}}
        counted = 0
        for d in common:
            c = domain_counts.get(d, 0)
            resp['domains'][d] = c
            counted += c

        resp['domains']['others'] = max(0, total - counted)

        top_domains = sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        resp['top_domains'] = [{ 'domain': d, 'count': c } for d,c in top_domains]

        return JsonResponse(resp)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def api_generate_uid(request):
    try:
        ok, res = DB2Query.runSelectQuery("SELECT UID FROM AUTHENTICATION WHERE UID IS NOT NULL")
        prefixes = {}
        if ok and res:
            for row in res:
                uid = (row.get('UID') or '').strip()
                m = re.match(r"^([A-Za-z]+)(\d+)$", uid)
                if m:
                    pfx = m.group(1).upper()
                    num = int(m.group(2))
                    width = len(m.group(2))
                    if pfx not in prefixes:
                        prefixes[pfx] = { 'max': num, 'width': width }
                    else:
                        if num > prefixes[pfx]['max']:
                            prefixes[pfx]['max'] = num
                        prefixes[pfx]['width'] = max(prefixes[pfx]['width'], width)

        if prefixes:
            counts = {}
            for row in res:
                uid = (row.get('UID') or '').strip()
                m = re.match(r"^([A-Za-z]+)(\d+)$", uid)
                if m:
                    pfx = m.group(1).upper()
                    counts[pfx] = counts.get(pfx, 0) + 1
            chosen = max(counts.items(), key=lambda x: x[1])[0]
            info = prefixes.get(chosen)
            max_num = info['max']
            width = info['width']
            new_num = max_num + 1
            new_uid = f"{chosen}{new_num:0{width}d}"
        else:
            new_uid = 'ABC001'

        exists_ok, exists_res = DB2Query.runSelectQuery(f"SELECT UID FROM AUTHENTICATION WHERE UID = '{new_uid}' FETCH FIRST 1 ROW ONLY")
        attempts = 0
        while exists_ok and exists_res and attempts < 1000:
            m = re.match(r"^([A-Za-z]+)(\d+)$", new_uid)
            if not m:
                new_uid = 'ABC001'
                break
            pfx = m.group(1)
            num = int(m.group(2)) + 1
            w = len(m.group(2))
            new_uid = f"{pfx}{num:0{w}d}"
            exists_ok, exists_res = DB2Query.runSelectQuery(f"SELECT UID FROM AUTHENTICATION WHERE UID = '{new_uid}' FETCH FIRST 1 ROW ONLY")
            attempts += 1

        return JsonResponse({'uid': new_uid})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def api_register_user(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST allowed'}, status=405)

    try:
        try:
            body = json.loads(request.body)
            name = body.get('name')
            email = body.get('email')
        except Exception:
            name = request.POST.get('name')
            email = request.POST.get('email')

        if not name or not email:
            return JsonResponse({'error': 'name and email are required'}, status=400)

        name_s = name.replace("'", "''")
        email_s = email.replace("'", "''")

        check_q = f"SELECT EMAIL FROM AUTHENTICATION WHERE EMAIL = '{email_s}' FETCH FIRST 1 ROW ONLY"
        okc, crec = DB2Query.runSelectQuery(check_q)
        if okc and crec:
            return JsonResponse({'error': 'Email already registered'}, status=400)

        new_uid = None
        for attempt in range(10):
            uid_resp = api_generate_uid(request)
            if isinstance(uid_resp, JsonResponse):
                data = json.loads(uid_resp.content)
                cand = data.get('uid')
            else:
                cand = 'ABC001'

            exists_q = f"SELECT UID FROM AUTHENTICATION WHERE UID = '{cand}' FETCH FIRST 1 ROW ONLY"
            okx, rx = DB2Query.runSelectQuery(exists_q)
            if not okx:
                continue
            if not rx:
                new_uid = cand
                break

        if not new_uid:
            return JsonResponse({'error': 'Unable to generate unique UID, try again'}, status=500)

        ok, pass_res = DB2Query.runSelectQuery("SELECT PASSWORD FROM AUTHENTICATION WHERE PASSWORD IS NOT NULL")
        existing_passwords = set()
        if ok and pass_res:
            for r in pass_res:
                p = r.get('PASSWORD')
                if p:
                    existing_passwords.add(str(p))

        password = None
        attempts = 0
        while attempts < 500:
            candidate = '{:04d}'.format(random.randint(0, 9999))
            if candidate not in existing_passwords:
                password = candidate
                break
            attempts += 1

        if not password:
            return JsonResponse({'error': 'Unable to generate unique password'}, status=500)

        flag = 'P'
        key = ''

        insert_sql = (
            "INSERT INTO AUTHENTICATION (UID, NAME, EMAIL, PASSWORD, FLAG, KEY) "
            f"VALUES ('{new_uid}', '{name_s}', '{email_s}', '{password}', '{flag}', '{key}')"
        )

        success, msg = DB2Query.runQuery(insert_sql)
        if not success:
            if isinstance(msg, str) and ('SQL0803N' in msg or 'SQLCODE=-803' in msg or '23505' in msg):
                retried = False
                for attempt in range(5):
                    uid_resp = api_generate_uid(request)
                    if isinstance(uid_resp, JsonResponse):
                        data = json.loads(uid_resp.content)
                        cand = data.get('uid')
                    else:
                        cand = None
                    if not cand:
                        continue
                    okx, rx = DB2Query.runSelectQuery(f"SELECT UID FROM AUTHENTICATION WHERE UID = '{cand}' FETCH FIRST 1 ROW ONLY")
                    if not okx:
                        continue
                    if rx:
                        continue
                    insert_sql = (
                        "INSERT INTO AUTHENTICATION (UID, NAME, EMAIL, PASSWORD, FLAG, KEY) "
                        f"VALUES ('{cand}', '{name_s}', '{email_s}', '{password}', '{flag}', '{key}')"
                    )
                    success2, msg2 = DB2Query.runQuery(insert_sql)
                    if success2:
                        new_uid = cand
                        success = True
                        msg = msg2
                        retried = True
                        break
                if not retried and not success:
                    return JsonResponse({'error': f'Failed to insert user after retry: {msg}'}, status=500)
            else:
                return JsonResponse({'error': f'Failed to insert user: {msg}'}, status=500)

        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_q = (
            "INSERT INTO activity (log_name, log_desc, log_date_time) "
            f"VALUES ('User Registration', 'Registered user {new_uid} ({name_s})', '{ts}')"
        )
        DB2Query.runQuery(log_q)

        pdf_url = f"/api/registration_pdf/{new_uid}/"

        return JsonResponse({'success': True, 'uid': new_uid, 'password': password, 'pdf_url': pdf_url})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def registration_pdf(request, uid):
    if not uid:
        return JsonResponse({'error': 'UID required'}, status=400)

    q = f"SELECT UID, NAME, EMAIL, PASSWORD, FLAG, KEY FROM AUTHENTICATION WHERE UID = '{uid}' FETCH FIRST 1 ROW ONLY"
    ok, res = DB2Query.runSelectQuery(q)
    if not ok or not res:
        return JsonResponse({'error': 'User not found'}, status=404)

    user = res[0]
    buffer = BytesIO()
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    title = Paragraph('HealthLedger - Patient Registration', styles['Title'])
    story.append(title)
    story.append(Spacer(1, 12))

    normal = styles['Normal']
    story.append(Paragraph(f"UID: {user.get('UID', '')}", normal))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"Name: {user.get('NAME', '')}", normal))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"Email: {user.get('EMAIL', '')}", normal))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"Temporary Password: {user.get('PASSWORD', '')}", normal))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"Flag: {user.get('FLAG', '')}", normal))
    story.append(Spacer(1, 12))
    story.append(Paragraph('Please change the temporary password on first login.', styles['Italic']))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename=registration_{uid}.pdf'
    return response

# ===================================================== PASSWORD RESET VIEWS =====================================================

def user_reset_password(request):
    return render(request, 'src/user/RESET.html')

def send_otp_email(email, otp_code):
    try:
        r = resend.Emails.send({
            "from": "healthledger@acadx.xyz",
            "to": email,
            "subject": "HealthLedger - Password Reset Code",
            "html": f"""
<!doctype html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="x-apple-disable-message-reformatting">
  <meta name="color-scheme" content="dark only">
  <meta name="supported-color-schemes" content="dark">
  <title>HealthLedger OTP</title>
  <style>
    .preheader {{ display:none!important; visibility:hidden; opacity:0; color:transparent; height:0; width:0; overflow:hidden; mso-hide:all; }}
    .btn:hover {{ filter:brightness(1.15); }}
    @media (max-width:600px){{
      .container {{ width:100%!important; }}
      .otp {{ font-size:28px!important; letter-spacing:8px!important; }}
    }}
  </style>
</head>
<body style="margin:0; padding:0; background:#0b0f16; color:#e5e7eb;">
  <span class="preheader">Your HealthLedger one-time passcode: {otp_code} (valid for 10 minutes)</span>

  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0b0f16;">
    <tr>
      <td align="center" style="padding:32px 16px;">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" class="container"
               style="width:600px; max-width:600px; background:#111827; border-radius:16px; overflow:hidden; box-shadow:0 10px 30px rgba(0,0,0,0.35);">
          <tr>
            <td align="center" style="padding:32px 24px 12px 24px;">
              <img src="https://i.ibb.co/rRgdJQR4/logo.png" alt="HealthLedger"
                   style="display:block; margin:0 auto 8px auto; border:0; outline:none; text-decoration:none; max-width:250px;">
            </td>
          </tr>

          <tr>
            <td align="center" style="padding:0 24px 4px 24px; font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
              <h1 style="margin:0; font-size:22px; line-height:1.4; font-weight:700; color:#f9fafb;">
                Password Reset Code
              </h1>
              <p style="margin:8px 0 0 0; font-size:14px; color:#cbd5e1;">
                Use this code to reset your password for <strong>HealthLedger</strong>.
              </p>
            </td>
          </tr>

          <tr>
            <td align="center" style="padding:20px 24px 8px 24px;">
              <div class="otp"
                   style="display:inline-block; font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace;
                          font-size:34px; letter-spacing:10px; color:#ffffff;
                          background:#0b1220; border:1px solid #1f2937; border-radius:12px;
                          padding:16px 24px; text-align:center;">
                {otp_code}
              </div>
            </td>
          </tr>

          <tr>
            <td align="center" style="padding:0 24px 24px 24px; font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
              <p style="margin:12px 0 0 0; font-size:13px; color:#9ca3af;">
                This code expires in <strong>10 minutes</strong> and can be used only once.
              </p>
              <p style="margin:6px 0 0 0; font-size:12px; color:#6b7280;">
                Didn't request this? You can safely ignore this email.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>

  <!--[if mso]>
  <style type="text/css">
    .otp {{ letter-spacing: 10px !important; }}
  </style>
  <![endif]-->
</body>
</html>
            """
        })
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

@csrf_exempt
def api_send_reset_otp(request):
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        
        email = data.get('email', '').strip().lower()
        
        if not email:
            return JsonResponse({'success': False, 'message': 'Email is required'}, status=400)
        
        # Check if user exists (P = Patient user)
        query = f"SELECT UID, EMAIL FROM AUTHENTICATION WHERE LOWER(EMAIL) = '{email}' AND FLAG = 'P'"
        success, result = DB2Query.runSelectQuery(query)
        
        if not success or not result:
            return JsonResponse({'success': False, 'message': 'No account found with this email'}, status=404)
        
        # Generate 6-digit OTP
        otp_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        # Store OTP with expiry time (10 minutes)
        expiry_time = datetime.now() + timedelta(minutes=10)
        OTP_STORAGE[email] = {
            'otp': otp_code,
            'expiry': expiry_time,
            'verified': False
        }
        
        # Send OTP email
        if send_otp_email(email, otp_code):
            return JsonResponse({'success': True, 'message': 'OTP sent successfully'})
        else:
            return JsonResponse({'success': False, 'message': 'Failed to send email'}, status=500)
            
    except json.JSONDecodeError as e:
        return JsonResponse({'success': False, 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': 'Server error'}, status=500)
    finally:
        print("="*80)

@csrf_exempt
def api_verify_reset_otp(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        
        email = data.get('email', '').strip().lower()
        otp = data.get('otp', '').strip()
        
        if not email or not otp:
            return JsonResponse({'success': False, 'message': 'Email and OTP are required'}, status=400)
    
        # Check if OTP exists
        if email not in OTP_STORAGE:
            return JsonResponse({'success': False, 'message': 'No OTP found for this email'}, status=404)
        
        otp_data = OTP_STORAGE[email]
        
        # Check if OTP is expired
        if datetime.now() > otp_data['expiry']:
            del OTP_STORAGE[email]
            return JsonResponse({'success': False, 'message': 'OTP has expired'}, status=400)
        
        # Verify OTP
        if otp_data['otp'] != otp:
            return JsonResponse({'success': False, 'message': 'Invalid OTP'}, status=400)
        
        # Mark OTP as verified
        OTP_STORAGE[email]['verified'] = True
        
        return JsonResponse({'success': True, 'message': 'OTP verified successfully'})
        
    except json.JSONDecodeError as e:
        return JsonResponse({'success': False, 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': 'Server error'}, status=500)
    finally:
        print("="*80)

@csrf_exempt
def api_reset_password(request):
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        
        email = data.get('email', '').strip().lower()
        new_password = data.get('new_password', '')
        
        if not email or not new_password:
            return JsonResponse({'success': False, 'message': 'Email and password are required'}, status=400)
        
        if email not in OTP_STORAGE or not OTP_STORAGE[email].get('verified', False):

            return JsonResponse({'success': False, 'message': 'OTP not verified'}, status=400)
        
        if datetime.now() > OTP_STORAGE[email]['expiry']:
            del OTP_STORAGE[email]
            return JsonResponse({'success': False, 'message': 'OTP has expired'}, status=400)
        
        query = f"UPDATE AUTHENTICATION SET PASSWORD = '{new_password}' WHERE LOWER(EMAIL) = '{email}' AND FLAG = 'P'"
        success, result = DB2Query.runQuery(query)
        
        if not success:
            return JsonResponse({'success': False, 'message': 'Failed to update password'}, status=500)
        
        # Clear OTP from storage
        del OTP_STORAGE[email]
        
        return JsonResponse({'success': True, 'message': 'Password reset successfully'})
        
    except json.JSONDecodeError as e:
        return JsonResponse({'success': False, 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': 'Server error'}, status=500)
    finally:
        print("="*80)

# ===================================================== API VIEWS =====================================================
