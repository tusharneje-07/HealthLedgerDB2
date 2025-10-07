import DB2QueryServer

a,b = DB2QueryServer.runQuery("SELECT * FROM register")
print(a,b)