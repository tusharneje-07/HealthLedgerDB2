from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from .DB2 import DB2Query
from datetime import datetime
from collections import defaultdict
from django.utils import timezone
import hashlib, base64
import json
import requests
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

# Load environment variables
load_dotenv()


# ===================================================== HIGH LEVEL VIEWS
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
    # Prefer the summed INVOICE_LOGS total as the source of truth for paid amount.
    # Fall back to register.PAID_AMT only when no logs exist for the invoice.
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

    # Collect invoice numbers for a single logs query
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

    # Assemble formatted result, prefer the sum of logs (if present) for paid_amount
    for row in invoices:
        amount = float(row.get("AMOUNT") or 0)
        invoice_num = row.get("INNVOCE_NUM")
        # Sum logs for this invoice if any exist
        detailed_logs = logs_by_invoice.get(invoice_num, [])
        sum_from_logs = sum(l.get("paid_amount_on_date", 0.0) for l in detailed_logs)

        # Use logs sum if it exists (>0), otherwise use the PAID_AMOUNT from the main query
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
    # Support both GET (render) and POST (form-based login)
    if request.method == 'GET':
        return render(request, 'src/management/LOGIN.html')

    username = request.POST.get('username') or request.POST.get('email')
    password = request.POST.get('password')
    user_type = request.POST.get('user_type') or 'S'  # Default to 'S' for staff
    
    # Key Based Login
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

                # set session values now (so we can return immediately)
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
                # Use plain text email in URL instead of base64
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
                # Use plain text email in URL instead of base64
                response = redirect('/user/'+email+'/')
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
                    email,
                    max_age=3 * 60 * 60,   # 3 hours in seconds
                    httponly=False,
                    secure=request.is_secure(),
                    samesite='Lax'
                )
                response.set_cookie(
                    'user_type',
                    'P',
                    max_age=3 * 60 * 60,   # 3 hours in seconds
                    httponly=False,
                    secure=request.is_secure(),
                    samesite='Lax'
                )
                return response

        # Failed login
        return render(request, 'src/management/LOGIN.html', {'error': 'Invalid UID or password'})
    return render(request, 'src/user/DASH.html')

def user_dashboard(request, user_email):
    auth_token = request.COOKIES.get('auth_token')
    if auth_token and request.session.get(f'{auth_token}_is_authenticated'):
        # user_email is already in plain text format, no need to decode
        return render(request, 'src/user/DASH.html', {'user_email_d': user_email, 'user_email': user_email})
    else:
        return redirect('/login/')
    
def user_invoices(request, user_email):
    auth_token = request.COOKIES.get('auth_token')
    if auth_token and request.session.get(f'{auth_token}_is_authenticated'):
        # user_email is already in plain text format, no need to decode
        return render(request, 'src/user/INVOICES.html', {'user_email_d': user_email, 'user_email': user_email})
    else:
        return redirect('/login/')
# ===================================================== USER VIEWS


def api_user_invoices(request, user_email):
    """Return invoices for the provided base64-encoded user email.
    URL: /api/user/invoices/<str:user_email>/
    """
    # decode base64 email
    try:
        decoded_email = base64.b64decode(user_email).decode('utf-8')
    except Exception:
        return JsonResponse({'error': 'Invalid encoded email'}, status=400)

    # sanitize
    email_s = decoded_email.replace("'", "''")

    # resolve UID
    uid_q = f"SELECT UID FROM AUTHENTICATION WHERE EMAIL = '{email_s}' FETCH FIRST 1 ROW ONLY"
    ok, uid_res = DB2Query.runSelectQuery(uid_q)
    if not ok or not uid_res:
        return JsonResponse([], safe=False)

    uid = uid_res[0].get('UID')
    if not uid:
        return JsonResponse([], safe=False)

    # fetch invoices for UID (aggregate paid amounts)
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
    

# ===================================================== HIGH LEVEL VIEWS

# ===================================================== API VIEWS

def get_data_by_uid(request):
    uid = request.GET.get('uid')
    if not uid:
        return JsonResponse({"error": "UID is required"}, status=400)

    # 🧩 Single optimized JOIN query to fetch both patient and payment info
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

    # Fetch invoice summary with aggregated paid amount (no N+1)
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

    # Fetch all logs for this invoice
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
    by = request.GET.get("by", "mode:cash|id:null")  # Default to cash payment

    # ✅ 1. Input validation
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

    # ✅ 2. Parse payment method from 'by' parameter
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

    # ✅ 3. Precompute values once
    remaining_amount = max(0, total_amount - paid_amount)
    current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ✅ 4. Run queries in sequence (minimal overhead)
    # Update register
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

    # ✅ 4. Return response
    return JsonResponse({"message": "Payment updated successfully"})

def recent_activity(request):
    if request.method == "GET":
        # Fetch last 10 records from DB2 using your helper function
        sql = "SELECT log_name, log_desc, log_date_time FROM activity ORDER BY log_date_time DESC FETCH FIRST 10 ROWS ONLY"
        success, result = DB2Query.runSelectQuery(sql)
        if success:
            # Convert DB2 result to desired JSON format
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
    # keep request usage to avoid linter warnings
    _ = request.GET.get('dummy')

    # Use invoice-level aggregation from INVOICE_LOGS to compute paid amounts,
    # then compute pending/paid customer counts per invoice to avoid relying on register.PAID_AMT.
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

        # Insert into patient_data
        patient_data_sql = f"""
            INSERT INTO patient_data (uid, username, innvoce_num, date, amount)
            VALUES ('{uid}', '{username}', '{innvoce_num}', '{date}', {amount})
        """
        a, b = DB2Query.runQuery(patient_data_sql)
         # Check if insertion was successful
        if not a:
            return JsonResponse({"error": f"Failed to insert into patient_data: {b}"}, status=500)

        # Insert into register with initial paid_amt as 0
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
    # support pagination (offset) and text search
    try:
        size = int(request.GET.get("size", 50))
        offset = int(request.GET.get("offset", 0))
    except ValueError:
        return JsonResponse({"error": "size Sand offset must be numbers"}, status=400)

    search = (request.GET.get('search') or '').strip()
    # optional date/status filters
    date_from = (request.GET.get('date_from') or '').strip()
    date_to = (request.GET.get('date_to') or '').strip()
    status = (request.GET.get('status') or '').strip().lower()  # expected: 'paid' or 'pending' or ''

    if size <= 0 or size > 1000 or offset < 0:
        return JsonResponse({"error": "Invalid size/offset"}, status=400)

    # Build optional WHERE clause for a basic text search (UID, USERNAME, INNVOCE_NUM)
    where_clause = ""
    wheres = []
    if search:
        s = search.replace("'", "''")
        wheres.append(
            f"(LOWER(p.USERNAME) LIKE LOWER('%{s}%') "
            f"OR LOWER(p.UID) LIKE LOWER('%{s}%') "
            f"OR LOWER(p.INNVOCE_NUM) LIKE LOWER('%{s}%'))"
        )
    # date filters assume DATE column is comparable using string ISO or DB2 compatible format
    if date_from:
        df = date_from.replace("'", "''")
        wheres.append(f"p.DATE >= '{df}'")
    if date_to:
        dt = date_to.replace("'", "''")
        wheres.append(f"p.DATE <= '{dt}'")

    where_clause = ''
    if wheres:
        where_clause = 'WHERE ' + ' AND '.join(wheres)

    # ✅ OPTIMIZATION 1: Use CTE for better query performance
    # ✅ OPTIMIZATION 2: Apply status filter in SQL, not Python
    # Pre-compute paid amounts in CTE, then filter by status in SQL
    
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
    
    # Add status filter to SQL if provided
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

    # Execute both queries in parallel
    parallel_queries = [count_query, invoice_query]
    success, results = DB2Query.runParallelQueries(parallel_queries, max_workers=10)
    
    if not success:
        return JsonResponse({"error": f"Failed to load data: {results}"}, status=500)

    # Parse results - results is a list of query results
    # First result is count query (single row), second is invoice query (multiple rows)
    total_count = 0
    invoices = []
    
    if len(results) >= 2:
        # First query result (count)
        count_result = results[0]
        if count_result and len(count_result) > 0:
            total_count = int(count_result[0].get('TOTAL') or count_result[0].get('total') or 0)
        
        # Second query result (invoices)
        invoices = results[1] if results[1] else []
    else:
        # Fallback - shouldn't happen but handle gracefully
        return JsonResponse({"error": "Unexpected query results format"}, status=500)

    if not invoices:
        # Return empty list and include X-Total-Count header
        resp = JsonResponse([], safe=False)
        resp['X-Total-Count'] = str(total_count)
        return resp

    # ✅ OPTIMIZATION 3: Fetch logs in a SINGLE optimized query instead of batches
    invoice_nums = [f"'{row['INNVOCE_NUM']}'" for row in invoices]
    invoice_num_list = ", ".join(invoice_nums)
    
    log_query = f"""
        SELECT INVOICE_NUMBER, LOG_DATE, PAID_AMOUNT_ON_DATE, LOG_REMARK
        FROM INVOICE_LOGS
        WHERE INVOICE_NUMBER IN ({invoice_num_list})
        ORDER BY INVOICE_NUMBER, LOG_DATE DESC
    """
    
    # Execute log query
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

    # ✅ Assemble result in memory (status already filtered in SQL)
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

    # Attach total count header
    resp = JsonResponse(formatted_result, safe=False)
    resp['X-Total-Count'] = str(total_count)
    
    return resp

def records_count(request):
    """Return the total number of records matching current filters.
       This endpoint returns JSON: { total: N }
    """
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

    # sanitize email to avoid breaking SQL
    email_s = user_email.replace("'", "''")

    # 1) Resolve UID for the email
    uid_q = f"SELECT UID FROM AUTHENTICATION WHERE EMAIL = '{email_s}' FETCH FIRST 1 ROW ONLY"
    ok, uid_res = DB2Query.runSelectQuery(uid_q)
    if not ok:
        return JsonResponse({"error": "Failed to resolve user"}, status=500)
    if not uid_res:
        return JsonResponse({"error": "User not found"}, status=404)

    uid = uid_res[0].get("UID")
    if not uid:
        return JsonResponse({"error": "User UID not found"}, status=404)

    # compute month/year values for payment summaries
    now = timezone.now()
    this_month = now.month
    this_year = now.year
    if this_month == 1:
        last_month = 12
        last_month_year = this_year - 1
    else:
        last_month = this_month - 1
        last_month_year = this_year

    # 2) Summary: aggregate counts and sums per invoice using invoice logs aggregation
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

    # 3) Payment summary: this_month and last_month sums using MONTH/YEAR to avoid date math
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

    # 4) Recent transactions: last 5 logs for user's invoices (status only 'paid' or 'pending')
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

            # Only two statuses: paid or pending
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
    """
    Initiate payment: receives amount, invoice_num, uid from frontend
    Creates Razorpay order and returns form data
    """
    if request.method != "POST":
        return JsonResponse({"error": "Only POST method allowed"}, status=405)
    
    try:
        # Get payment details from POST
        data = json.loads(request.body)
        amount = float(data.get('amount', 0))
        invoice_num = data.get('invoice_num', '')
        uid = data.get('uid', '')
        
        if not amount or not invoice_num or not uid:
            return JsonResponse({"error": "Missing required fields"}, status=400)
        
        # Validate amount is positive
        if amount <= 0:
            return JsonResponse({"error": "Invalid amount"}, status=400)
        
        # Convert to paise for Razorpay (INR smallest unit)
        amount_in_paise = int(amount * 100)
        
        # Initialize Razorpay client
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        
        # Create Razorpay order
        order_data = {
            'amount': amount_in_paise,
            'currency': 'INR',
            'payment_capture': 1,  # Auto-capture payment
            'notes': {
                'invoice_num': invoice_num,
                'uid': uid
            }
        }
        
        order = client.order.create(data=order_data)
        order_id = order['id']
        
        # Return payment details to frontend
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
    """
    Verify Razorpay payment signature and update invoice payment record
    This is called after Razorpay payment success
    """
    if request.method != "POST":
        return JsonResponse({"error": "Only POST method allowed"}, status=405)
    
    try:
        # Get payment verification data
        razorpay_payment_id = request.POST.get('razorpay_payment_id')
        razorpay_order_id = request.POST.get('razorpay_order_id')
        razorpay_signature = request.POST.get('razorpay_signature')
        
        # Get invoice details
        invoice_num = request.POST.get('invoice_num')
        uid = request.POST.get('uid')
        amount = request.POST.get('amount')
        total_amount = request.POST.get('total_amount')
        
        if not all([razorpay_payment_id, razorpay_order_id, razorpay_signature, invoice_num, uid, amount, total_amount]):
            return JsonResponse({"error": "Missing required fields"}, status=400)
        
        # Initialize Razorpay client
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        
        # Verify payment signature
        params_dict = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        }
        
        try:
            client.utility.verify_payment_signature(params_dict)
        except razorpay.errors.SignatureVerificationError:
            return JsonResponse({"error": "Payment signature verification failed"}, status=400)
        
        # Payment verified successfully - update database
        paid_amount = float(amount)
        total_amt = float(total_amount)
        
        # Sanitize inputs
        uid_s = uid.replace("'", "''")
        invoice_s = invoice_num.replace("'", "''")
        payment_id_s = razorpay_payment_id.replace("'", "''")
        
        # Compute remaining
        remaining_amount = max(0, total_amt - paid_amount)
        current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Update register table
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
        
        # Return success response
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
    """
    Placeholder for Razorpay payment integration.
    Currently not in use - payments are handled via /api/initiate_payment/ and /api/verify_payment/
    
    To implement full Razorpay integration:
    1. Create Payment model
    2. Set up Razorpay client with API keys
    3. Implement order creation and verification
    """
    return JsonResponse({
        "error": "This endpoint is deprecated. Use /api/initiate_payment/ and /api/verify_payment/ instead."
    }, status=501)

def razorpay_payment_window(request):
    """
    Render the Razorpay payment window (opens in popup)
    """
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
    
    # Create Razorpay order
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

# ===================================================== ANALYTICS VIEWS
def analytics_dashboard(request):
    """Render the main analytics dashboard page."""
    auth_token = request.COOKIES.get('auth_token')
    if auth_token and request.session.get(f'{auth_token}_is_authenticated'):
        return render(request, 'src/management/ANALYTICS.html')
    else:
        return redirect('/login')

def api_financial_summary(request):
    """
    Return JSON data for total revenue, outstanding, and monthly trends.
    Endpoint: /api/financial_summary/
    """
    try:
        # Total revenue from all invoices (from PATIENT_DATA table)
        total_revenue_query = """
            SELECT COALESCE(SUM(AMOUNT), 0) AS TOTAL_REVENUE
            FROM PATIENT_DATA
        """
        
        # Total collected payments
        total_collected_query = """
            SELECT COALESCE(SUM(PAID_AMOUNT_ON_DATE), 0) AS TOTAL_COLLECTED
            FROM INVOICE_LOGS
        """
        
        # Outstanding balance - calculate from patient data minus total paid
        outstanding_query = """
            SELECT COALESCE(SUM(p.AMOUNT) - SUM(COALESCE(il.TOTAL_PAID, 0)), 0) AS OUTSTANDING
            FROM PATIENT_DATA p
            LEFT JOIN (
                SELECT INVOICE_NUMBER, SUM(PAID_AMOUNT_ON_DATE) AS TOTAL_PAID
                FROM INVOICE_LOGS
                GROUP BY INVOICE_NUMBER
            ) il ON p.INNVOCE_NUM = il.INVOICE_NUMBER
        """
        
        # Monthly revenue trend (last 12 months)
        monthly_query = """
            SELECT 
                SUBSTR(CHAR(LOG_DATE), 1, 7) AS MONTH,
                COALESCE(SUM(PAID_AMOUNT_ON_DATE), 0) AS REVENUE
            FROM INVOICE_LOGS
            WHERE LOG_DATE >= CURRENT_DATE - 12 MONTHS
            GROUP BY SUBSTR(CHAR(LOG_DATE), 1, 7)
            ORDER BY MONTH ASC
        """
        
        # Execute queries
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
    """
    Return patient-related statistics and spending patterns.
    Endpoint: /api/patient_stats/
    """
    try:
        # Total unique patients
        total_patients_query = """
            SELECT COUNT(DISTINCT UID) AS TOTAL_PATIENTS
            FROM PATIENT_DATA
        """
        
        # Average spending per patient
        avg_spending_query = """
            SELECT COALESCE(AVG(AMOUNT), 0) AS AVG_SPENDING
            FROM PATIENT_DATA
        """
        
        # Repeat patients (more than one invoice)
        repeat_patients_query = """
            SELECT COUNT(*) AS REPEAT_PATIENTS
            FROM (
                SELECT UID
                FROM PATIENT_DATA
                GROUP BY UID
                HAVING COUNT(*) > 1
            ) AS repeat
        """
        
        # Top 10 paying patients
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
        
        # Execute queries
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
    """
    Return user activity counts and system logs.
    Endpoint: /api/activity_trends/
    """
    try:
        # Invoice volume trend (last 12 months)
        invoice_volume_query = """
            SELECT 
                SUBSTR(CHAR(DATE), 1, 7) AS MONTH,
                COUNT(*) AS COUNT
            FROM PATIENT_DATA
            WHERE DATE >= CURRENT_DATE - 12 MONTHS
            GROUP BY SUBSTR(CHAR(DATE), 1, 7)
            ORDER BY MONTH ASC
        """
        
        # Recent activity logs (last 10)
        recent_logs_query = """
            SELECT LOG_NAME, LOG_DESC, LOG_DATE_TIME
            FROM ACTIVITY
            ORDER BY LOG_DATE_TIME DESC
            FETCH FIRST 10 ROWS ONLY
        """
        
        # Execute queries
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
    """
    Return breakdown of payments by mode.
    Endpoint: /api/payment_modes/
    """
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
    """
    Return complete list of all patients with their invoice and payment status.
    Endpoint: /api/patients_list/
    """
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
    """
    Generate AI-powered insights using Groq API (llama-3.1-8b-instant).
    Collects analytics data, constructs a structured prompt, calls the Groq model,
    and returns insights with highlights and confidence.
    
    Security: API key is read from .env, never exposed to client.
    Endpoint: /api/ai_insights/
    """
   
    try:
        # Read Groq configuration from environment
        groq_api_key = os.getenv('GROQ_API_KEY')
        groq_model = os.getenv('GROQ_MODEL', 'llama-3.1-8b-instant')
        
        if not groq_api_key:
            return JsonResponse({
                "insights_text": "AI insights unavailable: API key not configured.",
                "highlights": ["Contact administrator to configure GROQ_API_KEY"],
                "confidence_score": 0.0
            })
        
        # Parse request body for optional parameters
        try:
            body = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            body = {}
        
        # Collect analytics data for the prompt
        # 1. Financial summary - Execute queries separately for accuracy
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
        
        # 2. Monthly revenue trend (last 6 months)
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
        
        # 3. Payment modes distribution
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
        
        # 4. Top paying patients
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
        
        # 5. Patient counts
        patient_stats_query = """
            SELECT 
                COUNT(DISTINCT UID) AS TOTAL_PATIENTS,
                COALESCE(AVG(AMOUNT), 0) AS AVG_INVOICE_AMOUNT
            FROM PATIENT_DATA
        """
        
        # Execute all queries in parallel
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
        
        # Parse collected data
        total_revenue = results[0][0]['TOTAL_REVENUE'] if results[0] else 0
        total_collected = results[1][0]['TOTAL_COLLECTED'] if len(results) > 1 and results[1] else 0
        total_outstanding = results[2][0]['TOTAL_OUTSTANDING'] if len(results) > 2 and results[2] else 0
        total_invoices = results[3][0]['TOTAL_INVOICES'] if len(results) > 3 and results[3] else 0
        avg_payment = results[4][0]['AVG_PAYMENT'] if len(results) > 4 and results[4] else 0
        
        monthly_data = results[5] if len(results) > 5 else []
        payment_modes = results[6] if len(results) > 6 else []
        top_patients = results[7] if len(results) > 7 else []
        patient_stats = results[8][0] if len(results) > 8 and results[8] else {}
        
        # Build structured context for Groq
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
        
        # Construct the prompt
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

        # Call Groq API
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
            
            # Extract insights text
            insights_text = groq_response['choices'][0]['message']['content']
            
            # Parse highlights from the response
            highlights = []
            lines = insights_text.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('- ') or line.startswith('• '):
                    highlights.append(line[2:])
                elif line.startswith(tuple(str(i) + '.' for i in range(1, 10))):
                    highlights.append(line.split('.', 1)[1].strip())
            
            # Limit highlights to 5
            highlights = highlights[:5]
            
            # Generate a simple confidence score based on data completeness
            confidence_score = 0.7  # Base confidence
            if len(monthly_data) >= 6:
                confidence_score += 0.1
            if len(payment_modes) >= 3:
                confidence_score += 0.1
            if float(total_revenue) > 0:
                confidence_score += 0.1
            
            confidence_score = min(confidence_score, 1.0)
            
            # Build response
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
            
            # Include raw response only for admin users (check user flag)
            auth_token = request.COOKIES.get('auth_token')
            if auth_token and request.session.get(f'{auth_token}_user_type') == 'S':
                response_data['raw_model_response'] = groq_response
            
            return JsonResponse(response_data)
            
        except requests.exceptions.RequestException as e:
            # Groq API call failed - return fallback insights
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
    """
    Generate and return a PDF report containing selected analytics sections.
    Uses ReportLab for server-side PDF generation (pure Python, no DLL dependencies).
    
    Security: Only authenticated users can generate reports.
    Endpoint: /api/generate_report/
    """
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    # Check authentication
    auth_token = request.COOKIES.get('auth_token')
    if not auth_token or not request.session.get(f'{auth_token}_is_authenticated'):
        return JsonResponse({"error": "Unauthorized"}, status=401)
    
    try:
        # Parse request body
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        
        sections = body.get('sections', [])
        orientation = body.get('orientation', 'portrait')
        
        if not sections:
            return JsonResponse({"error": "No sections selected"}, status=400)
        
        # Collect data for selected sections
        report_data = {
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'orientation': orientation,
            'sections': {}
        }
        
        # Map section IDs to data fetching functions
        if 'kpi-section' in sections:
            # Total Revenue from patient invoices
            total_revenue_query = """
                SELECT COALESCE(SUM(AMOUNT), 0) AS TOTAL_REVENUE
                FROM PATIENT_DATA
            """
            
            # Total Collected from payment logs
            total_collected_query = """
                SELECT COALESCE(SUM(PAID_AMOUNT_ON_DATE), 0) AS TOTAL_COLLECTED
                FROM INVOICE_LOGS
            """
            
            # Outstanding = Total invoiced - Total paid (grouped by invoice to avoid double counting)
            outstanding_query = """
                SELECT COALESCE(SUM(p.AMOUNT) - SUM(COALESCE(il.TOTAL_PAID, 0)), 0) AS OUTSTANDING
                FROM PATIENT_DATA p
                LEFT JOIN (
                    SELECT INVOICE_NUMBER, SUM(PAID_AMOUNT_ON_DATE) AS TOTAL_PAID
                    FROM INVOICE_LOGS
                    GROUP BY INVOICE_NUMBER
                ) il ON p.INNVOCE_NUM = il.INVOICE_NUMBER
            """
            
            # Total Patients count
            patient_count_query = """
                SELECT COUNT(DISTINCT UID) AS TOTAL_PATIENTS
                FROM PATIENT_DATA
            """
            
            # Execute all queries
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
            # Fetch payment modes (case-insensitive grouping)
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
                        'username': row['USERNAME'],  # FIXED: Changed from 'name' to 'username'
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
        
        # Generate PDF using ReportLab
        try:
            pdf_bytes = generate_reportlab_pdf(report_data, sections, orientation)
            
            # Verify PDF is valid
            if len(pdf_bytes) == 0:
                raise Exception("Generated PDF is empty")
            
            if not pdf_bytes.startswith(b'%PDF'):
                raise Exception("Generated file is not a valid PDF")
            
            # Return PDF
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

    # Set page size based on orientation
    pagesize = landscape(A4) if orientation == 'landscape' else A4
    page_width = pagesize[0]
    page_height = pagesize[1]

    # Create PDF document with minimal margins
    doc = SimpleDocTemplate(
        buffer,
        pagesize=pagesize,
        rightMargin=0.5*inch,
        leftMargin=0.5*inch,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch
    )

    # Calculate usable width
    usable_width = page_width - 1*inch  # Total width minus margins

    # Container for PDF elements
    story = []

    # Define styles with Times New Roman
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

    # Modern Title Header with colored background - compact
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

    # KPI Section - Compact modern cards
    if 'kpi-section' in sections and 'kpi' in report_data['sections']:
        kpi = report_data['sections']['kpi']
        story.append(Paragraph("Key Performance Indicators", heading_style))

        # Create compact KPI cards using full width
        col_width = usable_width / 4
        kpi_cards = [
            ['Total Revenue', 'Collected Payments', 'Outstanding Balance', 'Total Patients'],
            [f"Rs. {kpi['total_revenue']:,.0f}", f"Rs. {kpi['total_collected']:,.0f}",
             f"Rs. {kpi['outstanding']:,.0f}", str(kpi['total_patients'])]
        ]

        kpi_table = Table(kpi_cards, colWidths=[col_width]*4)
        kpi_table.setStyle(TableStyle([
            # Header row
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

            # Values row
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

            # Grid
            ('GRID', (0, 0), (-1, -1), 1.5, colors.white),
        ]))

        story.append(kpi_table)
        story.append(Spacer(1, 0.15*inch))

    # Revenue Trend Section - With Bar Chart side-by-side with table
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

    # Payment Modes Section - Compact with Pie Chart
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

    # Top Patients Section - Compact full-width table
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

    # Invoice Volume Section - Compact
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

    # Activity Logs Section - Compact full width
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

    # Patients List Section - Compact full width
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

    # AI Insights Section - fetch from local API and render
    # if 'ai-insights-section' in sections:
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

                print(f"DEBUG: AI Insights fetched - {insights_text}")  # Debug log
                # Render insights text (split by double newlines for paragraphs)
                if insights_text:
                    for part in insights_text.split('\n\n'):
                        # Keep line breaks inside paragraph
                        part_safe = part.replace('\n', '<br/>')
                        story.append(Paragraph(part_safe, normal_style))
                        story.append(Spacer(1, 0.08*inch))
                    ai_paragraphs_added = True

                # Render highlights as a compact table / list
                if highlights:
                    # Render highlights as a simple paragraph list (bulleted, compact)
                    safe_lines = []
                    for h in highlights:
                        # basic HTML-escape and truncate to keep layout tidy
                        s = str(h).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', ' ')
                        if len(s) > 280:
                            s = s[:277] + '...'
                        safe_lines.append('• ' + s)
                    highlights_text = '<br/>'.join(safe_lines)
                    story.append(Paragraph(highlights_text, normal_style))
                    story.append(Spacer(1, 0.08*inch))
                    ai_paragraphs_added = True

                # Render confidence and references in a small table
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

        # If nothing added, add a placeholder note
        if not ai_paragraphs_added:
            story.append(Paragraph("AI Insights are unavailable.", small_style))
            story.append(Spacer(1, 0.08*inch))

    # Compact Footer
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

    # Build PDF
    doc.build(story)

    # Get PDF bytes
    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes
    

# ===================================================== ANALYTICS VIEWS

# ===================================================== API VIEWS

# New API endpoints for CREATE form enhancements
def api_get_all_uids(request):
    """Get all unique UIDs with their usernames from AUTHENTICATION table"""
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
    """Generate a unique invoice number based on existing invoices"""
    query = """
        SELECT INNVOCE_NUM 
        FROM patient_data 
        ORDER BY REC_NUMBER DESC 
        FETCH FIRST 1 ROW ONLY
    """
    success, result = DB2Query.runSelectQuery(query)
    
    if not success or not result:
        # If no invoices exist, start with INV00000001
        new_invoice_num = "INV00000001"
    else:
        last_invoice = result[0].get("INNVOCE_NUM", "INV00000000")
        # Extract the numeric part and increment
        try:
            num_part = int(last_invoice.replace("INV", ""))
            new_num = num_part + 1
            new_invoice_num = f"INV{new_num:08d}"
        except:
            new_invoice_num = "INV00000001"
    
    return JsonResponse({"invoice_number": new_invoice_num})

def api_get_user_by_uid(request):
    """Get user details by UID"""
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