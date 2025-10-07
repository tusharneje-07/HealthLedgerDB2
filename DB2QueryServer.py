from flask import Flask, jsonify
import ibm_db
import urllib.parse

app = Flask(__name__)

# -------------------- DB2 CONFIG --------------------
dsn_hostname = "localhost"
dsn_uid = "db2admin"
dsn_pwd = "2425455"
dsn_database = "HOSPITAL"
dsn_port = "25000"
dsn_protocol = "TCPIP"

dsn = (
    f"DATABASE={dsn_database};"
    f"HOSTNAME={dsn_hostname};"
    f"PORT={dsn_port};"
    f"PROTOCOL={dsn_protocol};"
    f"UID={dsn_uid};"
    f"PWD={dsn_pwd};"
)

# -------------------- DB2 FUNCTIONS --------------------
def runQuery(query):
    try:
        conn = ibm_db.connect(dsn, "", "")
        ibm_db.autocommit(conn, ibm_db.SQL_AUTOCOMMIT_ON)
        ibm_db.exec_immediate(conn, "SET CURRENT SCHEMA = NEJET")
        ibm_db.exec_immediate(conn, query)
        ibm_db.close(conn)
        return True, "Query executed successfully"
    except Exception as e:
        return False, str(e)


def runSelectQuery(query):
    try:
        conn = ibm_db.connect(dsn, "", "")
        ibm_db.autocommit(conn, ibm_db.SQL_AUTOCOMMIT_ON)
        ibm_db.exec_immediate(conn, "SET CURRENT SCHEMA = NEJET")
        stmt = ibm_db.exec_immediate(conn, query)

        result = []
        row = ibm_db.fetch_assoc(stmt)
        while row:
            result.append(row)
            row = ibm_db.fetch_assoc(stmt)

        ibm_db.close(conn)
        return True, result
    except Exception as e:
        return False, str(e)


# -------------------- API ROUTES --------------------
@app.route('/run/<path:quest>', methods=['GET'])
def execute_query(quest):
    # Decode and clean query (remove surrounding quotes)
    query = urllib.parse.unquote(quest).strip()
    if query.startswith('"') and query.endswith('"'):
        query = query[1:-1]
    success, result = runQuery(query)
    if success:
        return jsonify({"status": True, "message": result})
    else:
        return jsonify({"status": False, "message": result}), 500


@app.route('/select/<path:quest>', methods=['GET'])
def select_query(quest):
    # Decode and clean query (remove surrounding quotes)
    query = urllib.parse.unquote(quest).strip()
    if query.startswith('"') and query.endswith('"'):
        query = query[1:-1]
    success, result = runSelectQuery(query)
    if success:
        return jsonify({"status": True, "data": result})
    else:
        return jsonify({"status": False, "message": result}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9999, debug=True)
    
    
# ------------------------------------------------------------------------
# > pip install flask ibm_db
# > python DB2QueryServer.py
# * Serving Flask app 'DB2QueryServer'
#  * Debug mode: on
# WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
#  * Running on all addresses (0.0.0.0)
#  * Running on http://127.0.0.1:9999 <------------------------- Localhost access
#  * Running on http://192.168.221.78:9999
# ------------------------------------------------------------------------
## Example fetch request from client (JavaScript):
# // Your SQL query
# const sqlQuery = 'SELECT * FROM PATIENT_DATA';

# // Encode the query to make it URL-safe
# const encodedQuery = encodeURIComponent(`"${sqlQuery}"`); // keeps quotes if needed

# // Fetch request
# fetch(`http://localhost:9999/select/${encodedQuery}`)
#   .then(response => response.json())
#   .then(data => {
#     console.log('Response from server:', data);
#   })
#   .catch(error => {
#     console.error('Error:', error);
#   });
# 
# # ------------------------------------------------------------------------
