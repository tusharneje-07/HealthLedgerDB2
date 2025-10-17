from flask import Flask, jsonify, request
import ibm_db
import urllib.parse
app = Flask(__name__)

# -------------------- DB2 CONFIG --------------------
# Update these variables with your DB2 credentials
dsn_hostname = "localhost"
dsn_uid = "db2admin"
dsn_pwd = "2425455"
dsn_database = "MAINFRM"
dsn_port = "25000"
dsn_protocol = "TCPIP"
schema = "NEJET"

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
        ibm_db.exec_immediate(conn, "SET CURRENT SCHEMA = {}".format(schema))
        ibm_db.exec_immediate(conn, query)
        ibm_db.close(conn)
        return True, "Query executed successfully"
    except Exception as e:
        return False, str(e)


def runSelectQuery(query):
    try:
        conn = ibm_db.connect(dsn, "", "")
        ibm_db.autocommit(conn, ibm_db.SQL_AUTOCOMMIT_ON)
        ibm_db.exec_immediate(conn, "SET CURRENT SCHEMA = {}".format(schema))
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
@app.route('/get/run/<path:quest>', methods=['GET'])
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

@app.route('/get/select/<path:quest>', methods=['GET'])
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

@app.route('/get/describe/<table_name>', methods=['GET'])
def describe_table(table_name):
    query = f"""
        SELECT
            colname AS column_name,
            typename AS data_type,
            length,
            scale,
            nulls AS nullable,
            default AS default_value
        FROM syscat.columns
        WHERE tabschema = '{schema.upper()}'
          AND tabname = '{table_name.upper()}'
        ORDER BY colno
    """
    success, result = runSelectQuery(query)
    if success:
        return jsonify({"status": True, "data": result})
    else:
        return jsonify({"status": False, "message": result}), 500

@app.route('/post/', methods=['POST'])
def post_query():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": False, "message": "Invalid JSON payload"}), 400

        query_type = data.get("type")
        query_content = data.get("query")

        if not query_type or not query_content:
            return jsonify({"status": False, "message": "Missing 'type' or 'query' in payload"}), 400

        query_type = query_type.lower()

        if query_type == "run":
            success, result = runQuery(query_content)
        elif query_type == "select":
            success, result = runSelectQuery(query_content)
        elif query_type == "describe":
            success, result = describe_table(query_content)
        else:
            return jsonify({"status": False, "message": f"Unknown query type '{query_type}'"}), 400

        if success:
            return jsonify({"status": True, "data": result})
        else:
            return jsonify({"status": False, "message": result}), 500

    except Exception as e:
        return jsonify({"status": False, "message": str(e)}), 500

@app.route('/get', methods=['GET'])
@app.route('/', methods=['GET'])
@app.route('/info', methods=['GET'])
def information():
    return """
    <!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DB2 Query Server API Documentation</title>
<style>
    /* --- General dark theme --- */
    body {
        background-color: #121212;
        color: #e0e0e0;
        font-family: 'Fira Code', monospace;
        line-height: 1.6;
        margin: 0;
        padding: 0;
    }
    a { color: #80cbc4; text-decoration: none; }
    a:hover { text-decoration: underline; }

    header {
        background-color: #1f1f1f;
        padding: 30px;
        text-align: center;
        border-bottom: 1px solid #333;
    }
    header h1 { margin: 0; font-size: 2em; color: #80cbc4; }
    header p { margin-top: 5px; color: #bbb; }

    main {
        max-width: 1000px;
        margin: 20px auto;
        padding: 20px;
    }

    h1, h2, h3 {
        color: #80cbc4;
        margin-top: 1.5em;
    }
    h2 { border-bottom: 2px solid #80cbc4; padding-bottom: 5px; }
    h3 { margin-top: 1.2em; }

    p, ul, li {
        color: #e0e0e0;
    }
    ul { padding-left: 20px; }

    /* Code blocks */
    pre {
        position: relative;
        background-color: #1e1e1e;
        color: #c5c8c6;
        padding: 16px;
        border-radius: 5px;
        overflow-x: auto;
        font-family: 'Fira Code', monospace;
        margin: 10px 0;
    }

    /* Copy button */
    .copy-btn {
        position: absolute;
        top: 8px;
        right: 8px;
        background-color: #333;
        border: none;
        color: #80cbc4;
        padding: 4px 8px;
        border-radius: 4px;
        cursor: pointer;
        font-size: 0.9em;
    }
    .copy-btn:hover {
        background-color: #444;
    }

    table {
        width: 100%;
        border-collapse: collapse;
        margin: 10px 0;
    }
    table, th, td {
        border: 1px solid #333;
    }
    th, td {
        padding: 10px;
        text-align: left;
    }
    th {
        background-color: #1f1f1f;
    }
    td {
        background-color: #1a1a1a;
    }

    footer {
        text-align: center;
        padding: 20px;
        color: #777;
        border-top: 1px solid #333;
        margin-top: 40px;
    }
</style>
</head>
<body>

<header>
    <h1>DB2 Query Server API Documentation</h1>
</header>

<main>

<h2>Overview</h2>
<p>The DB2 Query Server API allows executing SQL queries against a DB2 database via RESTful endpoints. You can perform <strong>SELECT</strong>, <strong>RUN</strong> (INSERT, UPDATE, DELETE, DDL), and <strong>DESCRIBE</strong> operations.</p>
<p>All queries are executed under the schema: <strong>NEJET</strong>.</p>

<h2>DB2 Connection Configuration</h2>
<p>This section explains the DSN (Data Source Name) configuration used to connect the Flask API to the DB2 database.</p>

<pre>
<button class="copy-btn">Copy</button>
dsn_hostname = "localhost"      # DB2 server hostname or IP
dsn_uid = "db2admin"            # Username for authentication
dsn_pwd = "2425455"             # Password for the DB2 user
dsn_database = "HOSPITAL"       # Target database
dsn_port = "25000"              # DB2 listening port
dsn_protocol = "TCPIP"          # Communication protocol
schema = "NEJET"                # Default schema for queries

dsn = (
    f"DATABASE={dsn_database};"
    f"HOSTNAME={dsn_hostname};"
    f"PORT={dsn_port};"
    f"PROTOCOL={dsn_protocol};"
    f"UID={dsn_uid};"
    f"PWD={dsn_pwd};"
)
</pre>

<h3>Parameter Breakdown</h3>
<table>
<tr><th>Parameter</th><th>Description</th><th>Notes / Reference</th></tr>
<tr><td>dsn_hostname</td><td>Hostname or IP of DB2 server</td><td>Use 'localhost' if local, or the server IP for remote.<br><a href="https://www.ibm.com/docs/en/db2/11.5?topic=SSGU8G_11.5.0/com.ibm.db2.luw.admin.cmd.doc/doc/c0021596.html" target="_blank">IBM Docs: Connecting Clients</a></td></tr>
<tr><td>dsn_uid</td><td>DB2 username for authentication</td><td>Ensure proper privileges to access the database.</td></tr>
<tr><td>dsn_pwd</td><td>Password for the DB2 user</td><td>Keep secure; prefer environment variables in production.</td></tr>
<tr><td>dsn_database</td><td>Name of target DB2 database</td><td>Directs queries to the correct database instance.</td></tr>
<tr><td>dsn_port</td><td>Port number DB2 listens on</td><td>Default: 50000. Ensure port is open.<br><a href="https://www.ibm.com/docs/en/db2/11.5?topic=SSGU8G_11.5.0/com.ibm.db2.luw.admin.inst.doc/doc/c0021556.html" target="_blank">IBM Docs: Port Configuration</a></td></tr>
<tr><td>dsn_protocol</td><td>Communication protocol</td><td>Usually TCPIP; can use SSL for secure connections.<br><a href="https://www.ibm.com/docs/en/db2/11.5?topic=connections-connectivity-using-cli-odbc" target="_blank">IBM Docs: CLI/ODBC Protocols</a></td></tr>
<tr><td>schema</td><td>Default schema for SQL queries</td><td>Allows queries without schema prefix.<br><a href="https://www.ibm.com/docs/en/db2/11.5?topic=objects-schemas" target="_blank">IBM Docs: Schemas</a></td></tr>
</table>

<p>Example Python usage:</p>
<pre>
<button class="copy-btn">Copy</button>
import ibm_db

conn = ibm_db.connect(dsn, "", "")
if conn:
    print("Connected successfully!")
    ibm_db.close(conn)
else:
    print("Connection failed.")
</pre>

<h2>API Endpoints</h2>

<h3>1. GET /get/run/&lt;query&gt;</h3>
<pre>
<button class="copy-btn">Copy</button>
GET http://localhost:9999/get/run/INSERT%20INTO%20PATIENT_DATA(ID,NAME)%20VALUES(1,'John')
</pre>

<h3>2. GET /get/select/&lt;query&gt;</h3>
<pre>
<button class="copy-btn">Copy</button>
GET http://localhost:9999/get/select/SELECT%20*%20FROM%20PATIENT_DATA
</pre>

<h3>3. GET /get/describe/&lt;table_name&gt;</h3>
<pre>
<button class="copy-btn">Copy</button>
GET http://localhost:9999/get/describe/PATIENT_DATA
</pre>

<h3>4. POST /post/</h3>
<p>Execute SQL queries using JSON payload. Payload must include:</p>
<table>
<tr><th>Field</th><th>Type</th><th>Description</th></tr>
<tr><td>type</td><td>string</td><td>Query type: select, run, describe</td></tr>
<tr><td>query</td><td>string</td><td>The SQL query or table name for describe</td></tr>
</table>

<p>Example payload:</p>
<pre>
<button class="copy-btn">Copy</button>
{
    "type": "select",
    "query": "SELECT * FROM PATIENT_DATA"
}
</pre>

<h2>Example Responses</h2>

<h3>Success (SELECT)</h3>
<pre>
<button class="copy-btn">Copy</button>
{
  "status": true,
  "data": [
    {"ID": 1, "NAME": "John"},
    {"ID": 2, "NAME": "Alice"}
  ]
}
</pre>

<h3>Success (RUN)</h3>
<pre>
<button class="copy-btn">Copy</button>
{
  "status": true,
  "data": "Query executed successfully"
}
</pre>

<h3>Error Response</h3>
<pre>
<button class="copy-btn">Copy</button>
{
  "status": false,
  "message": "Table does not exist"
}
</pre>

<h2>Example Usage (JavaScript)</h2>
<pre>
<button class="copy-btn">Copy</button>
const sqlQuery = "SELECT * FROM PATIENT_DATA";
const payload = { type: "select", query: sqlQuery };

fetch("http://localhost:9999/post/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
})
.then(res => res.json())
.then(data => console.log(data))
.catch(err => console.error(err));
</pre>

</main>

<footer>
&copy; 2025 DB2 Query Server | Created by Tushar Neje
</footer>

<script>
document.querySelectorAll('.copy-btn').forEach(button => {
    button.addEventListener('click', () => {
        const code = button.parentElement.innerText.replace('Copy','').trim();
        navigator.clipboard.writeText(code).then(() => {
            button.innerText = 'Copied!';
            setTimeout(() => { button.innerText = 'Copy'; }, 1500);
        });
    });
});
</script>

</body>
</html>

"""

@app.route('/', methods=['POST'])
def information_post():
    return jsonify({
  "title": "DB2 Query Server API Documentation",
  "theme": "dark",
  "overview": {
    "description": "The DB2 Query Server API allows executing SQL queries against a DB2 database via RESTful endpoints. You can perform SELECT, RUN (INSERT, UPDATE, DELETE, DDL), and DESCRIBE operations.",
    "schema": "NEJET"
  },
  "db2_configuration": {
    "dsn": {
      "dsn_hostname": "localhost",
      "dsn_uid": "db2admin",
      "dsn_pwd": "2425455",
      "dsn_database": "HOSPITAL",
      "dsn_port": "25000",
      "dsn_protocol": "TCPIP",
      "schema": "NEJET",
      "dsn_string": "DATABASE=HOSPITAL;HOSTNAME=localhost;PORT=25000;PROTOCOL=TCPIP;UID=db2admin;PWD=2425455;"
    },
    "parameters": [
      {
        "name": "dsn_hostname",
        "description": "Hostname or IP of DB2 server",
        "notes": "Use 'localhost' if local, or the server IP for remote.",
        "reference": "https://www.ibm.com/docs/en/db2/11.5?topic=SSGU8G_11.5.0/com.ibm.db2.luw.admin.cmd.doc/doc/c0021596.html"
      },
      {
        "name": "dsn_uid",
        "description": "DB2 username for authentication",
        "notes": "Ensure proper privileges to access the database."
      },
      {
        "name": "dsn_pwd",
        "description": "Password for the DB2 user",
        "notes": "Keep secure; prefer environment variables in production."
      },
      {
        "name": "dsn_database",
        "description": "Name of target DB2 database",
        "notes": "Directs queries to the correct database instance."
      },
      {
        "name": "dsn_port",
        "description": "Port number DB2 listens on",
        "notes": "Default: 50000. Ensure port is open.",
        "reference": "https://www.ibm.com/docs/en/db2/11.5?topic=SSGU8G_11.5.0/com.ibm.db2.luw.admin.inst.doc/doc/c0021556.html"
      },
      {
        "name": "dsn_protocol",
        "description": "Communication protocol",
        "notes": "Usually TCPIP; can use SSL for secure connections.",
        "reference": "https://www.ibm.com/docs/en/db2/11.5?topic=connections-connectivity-using-cli-odbc"
      },
      {
        "name": "schema",
        "description": "Default schema for SQL queries",
        "notes": "Allows queries without schema prefix.",
        "reference": "https://www.ibm.com/docs/en/db2/11.5?topic=objects-schemas"
      }
    ],
    "example_python": "import ibm_db\n\nconn = ibm_db.connect(dsn, '', '')\nif conn:\n    print('Connected successfully!')\n    ibm_db.close(conn)\nelse:\n    print('Connection failed.')"
  },
  "api_endpoints": [
    {
      "method": "GET",
      "endpoint": "/get/run/<query>",
      "description": "Execute non-select SQL queries such as INSERT, UPDATE, DELETE, CREATE, ALTER.",
      "example": "GET http://localhost:9999/get/run/INSERT%20INTO%20PATIENT_DATA(ID,NAME)%20VALUES(1,'John')"
    },
    {
      "method": "GET",
      "endpoint": "/get/select/<query>",
      "description": "Execute SELECT queries and return results as JSON.",
      "example": "GET http://localhost:9999/get/select/SELECT%20*%20FROM%20PATIENT_DATA"
    },
    {
      "method": "GET",
      "endpoint": "/get/describe/<table_name>",
      "description": "Get table metadata including column name, type, length, nullable, and default value.",
      "example": "GET http://localhost:9999/get/describe/PATIENT_DATA"
    },
    {
      "method": "POST",
      "endpoint": "/post/",
      "description": "Execute SQL queries using JSON payload. Payload must include 'type' and 'query'.",
      "payload_example": {
        "type": "select",
        "query": "SELECT * FROM PATIENT_DATA"
      }
    }
  ],
  "example_responses": {
    "select_success": {
      "status": True,
      "data": [
        {"ID": 1, "NAME": "John"},
        {"ID": 2, "NAME": "Alice"}
      ]
    },
    "run_success": {
      "status": True,
      "data": "Query executed successfully"
    },
    "error": {
      "status": False,
      "message": "Table does not exist"
    }
  },
  "notes": [
    "Use URL encoding for GET requests.",
    "POST requests allow longer queries safely via JSON.",
    "Autocommit is enabled; no rollback is implemented.",
    "Only allowed query types for POST: select, run, describe.",
    "Validate inputs in production to prevent SQL injection.",
    "All results are returned in JSON format."
  ],
  "example_usage_js": "const sqlQuery = 'SELECT * FROM PATIENT_DATA';\nconst payload = { type: 'select', query: sqlQuery };\n\nfetch('http://localhost:9999/post/', {\n    method: 'POST',\n    headers: { 'Content-Type': 'application/json' },\n    body: JSON.stringify(payload)\n})\n.then(res => res.json())\n.then(data => console.log(data))\n.catch(err => console.error(err));"
})



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
