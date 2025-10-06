import ibm_db

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

def runQuery(query):
    try:
        conn = ibm_db.connect(dsn, "", "")
        ibm_db.autocommit(conn, ibm_db.SQL_AUTOCOMMIT_ON)
        ibm_db.exec_immediate(conn, "SET CURRENT SCHEMA = NEJET")
        stmt = ibm_db.exec_immediate(conn, query)
        ibm_db.close(conn)
        return True, stmt
    except Exception as e:
        return False, str(e)

def runSelectQuery(query):
    """Executes SELECT query and returns list of dictionaries"""
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