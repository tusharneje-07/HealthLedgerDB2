import DB2Query

a,b = DB2Query.runQuery("SELECT * FROM register")
print(a,b)