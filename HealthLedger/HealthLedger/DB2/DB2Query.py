import ibm_db
from multiprocessing import Pool
from functools import partial

dsn_hostname = "localhost"
dsn_uid = "db2admin"
dsn_pwd = "2425455"
dsn_database = "HOSPITAL"
dsn_port = "25000"
dsn_protocol = "TCPIP"
dsn_schema = "NEJET"

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
        ibm_db.exec_immediate(conn, f"SET CURRENT SCHEMA = {dsn_schema}")
        stmt = ibm_db.exec_immediate(conn, query)
        ibm_db.close(conn)
        return True, stmt
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

def _execute_single_query(query):
    return runSelectQuery(query)

def runParallelQueries(queries, max_workers=None):
    if not queries:
        return True, []
    
    try:
        with Pool(processes=max_workers) as pool:
            results = pool.map(_execute_single_query, queries)
        
        # Check if any query failed
        failed = [r for r in results if not r[0]]
        if failed:
            errors = "; ".join([r[1] for r in failed])
            return False, f"Some queries failed: {errors}"
        
        return True, [data for success, data in results]
    except Exception as e:
        return False, str(e)