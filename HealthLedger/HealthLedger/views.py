from django.shortcuts import render
from django.http import JsonResponse
from . import DB2Query
import ibm_db
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
        "remark": remark,
    }

    return JsonResponse([send_data], safe=False)

def update_payment(request):
    uid = request.GET.get("uid")
    invoice_num = request.GET.get("invoice_num")
    paid_amount = request.GET.get("paid_amount")

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
        print(a,b)
        return JsonResponse({"message": "Payment updated successfully"})
    else:
        return JsonResponse({"error": f"Failed to update payment: {msg}"}, status=500)
    
def load_data(request):
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
        FETCH FIRST 100 ROWS ONLY
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