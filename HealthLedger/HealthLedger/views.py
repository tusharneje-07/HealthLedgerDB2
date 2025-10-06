from django.shortcuts import render
from django.http import JsonResponse
from . import DB2Query
import ibm_db

def CREATE(request):
    return render(request, 'src/CREATE.html')
def UPDATE(request):
    return render(request, 'src/UPDATE.html')

def get_data_by_uid(request):
    uid = request.GET.get('uid')  # Get the UID from query params
    if not uid:
        return JsonResponse({"error": "UID is required"}, status=400)

    # Fetch data from the database using the DB2Query module
    query = f"SELECT * FROM patient_data WHERE uid = '{uid}'"
    success, result = DB2Query.runSelectQuery(query)

    if success and result:
        query = f"SELECT * FROM register WHERE uid = '{result[0]['UID']}' AND INNVOCE_NUM = '{result[0]['INNVOCE_NUM']}'"
        payment_done_success, payment_done = DB2Query.runSelectQuery(query)
        if payment_done_success and payment_done:
            send_data = {
                "recNumber": result[0]['REC_NUMBER'],
                "uid": result[0]['UID'],
                "username": result[0]['USERNAME'],
                "invoiceNum": result[0]['INNVOCE_NUM'],
                "date": str(result[0]['DATE']),
                "amount": float(result[0]['AMOUNT']),
                "paidAmount": float(payment_done[0]['PAID_AMT']),
                "remark": "Paid" if payment_done[0]['PAID_AMT'] >= result[0]['AMOUNT'] else "Pending",
            }
            print(send_data)
            return JsonResponse([send_data], safe=False)
        
    return JsonResponse([], safe=False)

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
        return JsonResponse({"message": "Payment updated successfully"})
    else:
        return JsonResponse({"error": f"Failed to update payment: {msg}"}, status=500)
    
def load_data(request):
    query = "SELECT * FROM patient_data FETCH FIRST 100 ROWS ONLY"
    success, result = DB2Query.runSelectQuery(query)

    if success and result:
        formatted_result = []
        for row in result:
            paid_query = f"SELECT PAID_AMT FROM register WHERE UID = '{row['UID']}' AND INNVOCE_NUM = '{row['INNVOCE_NUM']}'"
            paid_success, paid_result = DB2Query.runSelectQuery(paid_query)
            formatted_result.append({
                "recNumber": row['REC_NUMBER'],
                "uid": row['UID'],
                "username": row['USERNAME'],
                "invoiceNum": row['INNVOCE_NUM'],
                "date": str(row['DATE']),
                "amount": float(row['AMOUNT']),
                "paidAmount": float(paid_result[0]['PAID_AMT']) if paid_success and paid_result else 0.0,
                "remark":  "Paid" if paid_result[0]['PAID_AMT'] >= row['AMOUNT'] else "Pending",
            })
        return JsonResponse(formatted_result, safe=False)
    
    if success:
        return JsonResponse(result, safe=False)
    else:
        return JsonResponse({"error": "Failed to load data"}, status=500)
