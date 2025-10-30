from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from .DB2 import DB2Query
from datetime import datetime
from collections import defaultdict
from django.utils import timezone
import hashlib, base64
from django.contrib.sessions.models import Session
import json
import requests
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import razorpay


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
                base64_encoded_email = base64.b64encode(email.encode()).decode()
                return redirect('/user/'+base64_encoded_email+'/')
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
                base64_encoded_email = base64.b64encode(email.encode()).decode()
                response = redirect('/user/'+base64_encoded_email+'/')
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
        user_email_d = base64.b64decode(user_email).decode()
        return render(request, 'src/user/DASH.html', {'user_email_d': user_email_d, 'user_email': user_email})
    else:
        return redirect('/login/')
    
def user_invoices(request, user_email):
    auth_token = request.COOKIES.get('auth_token')
    if auth_token and request.session.get(f'{auth_token}_is_authenticated'):
        email = base64.b64decode(user_email).decode()
        return render(request, 'src/user/INVOICES.html', {'user_email_d': email, 'user_email': user_email})
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

    # Parse results - first query is count, second is invoices
    total_count = 0
    invoices = []
    
    # Count query returns 1 row, invoice query returns multiple
    # Separate by checking structure
    count_result = None
    invoice_result = []
    
    for row in results:
        if 'TOTAL' in row or 'total' in row:
            if count_result is None:
                count_result = row
        else:
            invoice_result.append(row)
    
    if count_result:
        total_count = int(count_result.get('TOTAL') or count_result.get('total') or 0)
    
    invoices = invoice_result

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

# ===================================================== API VIEWS