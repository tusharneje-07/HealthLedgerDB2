from django.shortcuts import render
from django.http import JsonResponse
from .DB2 import DB2Query
from datetime import datetime

def CREATE(request):
    return render(request, 'src/CREATE.html')
def UPDATE(request):
    return render(request, 'src/UPDATE.html')

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
        WHERE p.INNVOCE_NUM = '{invoice_num}'
        FETCH FIRST 1 ROW ONLY
    """

    success, result = DB2Query.runSelectQuery(query)
    if not success or not result:
        return JsonResponse([], safe=False)

    row = result[0]
    amount = float(row['AMOUNT'])
    
    paid_amount = 0
    
    query = f"SELECT PAID_AMOUNT_ON_DATE FROM INVOICE_LOGS WHERE INVOICE_NUMBER = '{invoice_num}' ORDER BY LOG_DATE DESC"
    a,b = DB2Query.runSelectQuery(query)
    print(a,b)
    if a and b and len(b) > 0:
        for log in b:
            if log['PAID_AMOUNT_ON_DATE'] is not None:
                paid_amount += float(log['PAID_AMOUNT_ON_DATE'])
    
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

def update_payment(request):
    uid = request.GET.get("uid")
    invoice_num = request.GET.get("invoice_num")
    paid_amount = request.GET.get("paid_amount")
    total_amount = request.GET.get("total_amount")

    if not uid or not invoice_num or not paid_amount:
        return JsonResponse({"error": "uid, invoice_num, and paid_amount are required"}, status=400)

    try:
        paid_amount = float(paid_amount)
    except ValueError:
        return JsonResponse({"error": "paid_amount must be a number"}, status=400)

    query = f"UPDATE register SET PAID_AMT = {paid_amount} WHERE UID = '{uid}' AND INNVOCE_NUM = '{invoice_num}'"
    
    success, msg = DB2Query.runQuery(query)
    if success:
        current_timestamp = datetime.now()
        query = f"INSERT INTO activity (log_name, log_desc, log_date_time) VALUES ('Payment Update', 'Payment updated of user {uid} to {paid_amount}', '{current_timestamp}')"
        a,b = DB2Query.runQuery(query)
        query = f"INSERT INTO INVOICE_LOGS (INVOICE_NUMBER, UID, LOG_DATE, AMOUNT, PAID_AMOUNT_ON_DATE, REMAINING_AMOUNT_ON_DATE, LOG_REMARK) VALUES ('{invoice_num}', '{uid}', '{current_timestamp}', {total_amount}, {paid_amount}, {max(0, float(paid_amount) - (float(total_amount) - float(paid_amount)))}, 'Payment updated');"
        
        a,b = DB2Query.runQuery(query)
        print(query,a,b)
        
        
        return JsonResponse({"message": "Payment updated successfully"})
    else:
        return JsonResponse({"error": f"Failed to update payment: {msg}"}, status=500)
    
def load_data(request):
    size = request.GET.get('size', 100)
    if not size and not str(size).isdigit():
        return JsonResponse({"error": "Size must be a number"}, status=400)
    size = int(size)
    if size <= 0 or size > 1000:
        return JsonResponse({"error": "Size must be between 1 and 1000"}, status=400)
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
        FETCH FIRST {size} ROWS ONLY
    """

    success, result = DB2Query.runSelectQuery(query)
    
    if not success:
        return JsonResponse({"error": "Failed to load data"}, status=500)
    
    formatted_result = []

    for row in result:
        amount = float(row['AMOUNT'])
        paid_amount = 0
    
        query = f"SELECT PAID_AMOUNT_ON_DATE FROM INVOICE_LOGS WHERE INVOICE_NUMBER = '{row['INNVOCE_NUM']}' ORDER BY LOG_DATE DESC"
        a,b = DB2Query.runSelectQuery(query)
        print(a,b)
        if a and b and len(b) > 0:
            for log in b:
                if log['PAID_AMOUNT_ON_DATE'] is not None:
                    paid_amount += float(log['PAID_AMOUNT_ON_DATE'])
        
        remark = "Paid" if paid_amount >= amount else "Pending"

        formatted_result.append({
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
        })

    return JsonResponse(formatted_result, safe=False)

def DASH(request):
    return render(request, 'src/DASH.html')


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
    # Query to get all necessary fields from patient_data and register
    query = """
        SELECT 
            p.REC_NUMBER,
            p.AMOUNT,
            COALESCE(r.PAID_AMT, 0) AS PAID_AMT
        FROM patient_data p
        LEFT JOIN register r
        ON p.UID = r.UID AND p.INNVOCE_NUM = r.INNVOCE_NUM
    """

    success, result = DB2Query.runSelectQuery(query)
    
    if not success:
        return JsonResponse({"error": "Failed to fetch stats"}, status=500)

    total_records = len(result)
    total_revenue = 0.0
    total_pending_amount = 0.0
    total_paid_customers = 0

    for row in result:
        amount = float(row['AMOUNT'])
        paid_amount = float(row['PAID_AMT'])
        total_revenue += amount
        if paid_amount >= amount:
            total_paid_customers += 1
        else:
            total_pending_amount += (amount - paid_amount)

    stats = {
        "total_records": total_records,
        "total_revenue": total_revenue,
        "total_pending_amount": total_pending_amount,
        "total_paid_customers": total_paid_customers
    }

    return JsonResponse(stats)


def VIEW_ALL(request):
    query = """
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
    """

    success, result = DB2Query.runSelectQuery(query)
    
    if not success:
        return JsonResponse({"error": "Failed to load data"}, status=500)
    
    formatted_result = []

    for row in result:
        amount = float(row['AMOUNT'])
        paid_amount = float(row['PAID_AMT']) if row['PAID_AMT'] is not None else 0.0
        remark = "Paid" if paid_amount >= amount else "Pending"

        formatted_result.append({
            "recNumber": row['REC_NUMBER'],
            "uid": row['UID'],
            "username": row['USERNAME'],
            "invoiceNum": row['INNVOCE_NUM'],
            "date": str(row['DATE']),
            "amount": amount,
            "paidAmount": paid_amount,
            "remark": remark,
        })
    return render(request, 'src/VIEW_ALL.html', {"records": formatted_result})


def ADD_NEW_DATA(request):
    print(request.GET)
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
    
def LOGOUT(request):
    return render(request, 'src/LOGOUT.html')

def detailed_invoice_view(request, invoice_num):
    # Fetch detailed invoice data based on invoice_num
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
        WHERE p.INNVOCE_NUM = '{invoice_num}'
        FETCH FIRST 1 ROW ONLY
    """

    success, result = DB2Query.runSelectQuery(query)
    
    if not success or not result:
        return JsonResponse({"error": "Invoice not found"}, status=404)
    
    row = result[0]
    amount = float(row['AMOUNT'])
    
    paid_amount = 0
    
    query = f"SELECT * FROM INVOICE_LOGS WHERE INVOICE_NUMBER = '{invoice_num}' ORDER BY LOG_DATE DESC"
    a,b = DB2Query.runSelectQuery(query)
    amount_logs = []
    if a and b and len(b) > 0:
        for log in b:
            if log['PAID_AMOUNT_ON_DATE'] is not None:
                amount_logs.append({
                    'date' : log['LOG_DATE'],
                    'paid_amount_on_date' : float(log['PAID_AMOUNT_ON_DATE']),
                    'log_remark' : log['LOG_REMARK']
                })
                paid_amount += float(log['PAID_AMOUNT_ON_DATE'])
    
    
    remark = "Paid" if paid_amount >= amount else "Pending"

    invoice_data = {
        "recNumber": row['REC_NUMBER'],
        "uid": row['UID'],
        "username": row['USERNAME'],
        "invoiceNum": row['INNVOCE_NUM'],
        "date": str(row['DATE']),
        "amount": amount,
        "paidAmount": paid_amount,
        "remainingAmount": max(0, amount - paid_amount),
        "detailed_logs": amount_logs,
        "remark": remark,
    }
    return JsonResponse(invoice_data)
    return render(request, 'src/INVOICE_DETAIL.html', {"invoice": invoice_data})