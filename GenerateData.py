import random
import datetime
import DB2Query

# Function to generate random name
def random_username():
    first_names = ["John", "Jane", "Mike", "Alice", "David", "Sophia", "Robert", "Emily", "Daniel", "Olivia"]
    last_names = ["Smith", "Johnson", "Brown", "Taylor", "Anderson", "Thomas", "Jackson", "White", "Harris", "Martin"]
    return random.choice(first_names) + " " + random.choice(last_names)

# Function to generate random date between 2020-01-01 and 2025-12-31
def random_date():
    start_date = datetime.date(2020, 1, 1)
    end_date = datetime.date(2025, 12, 31)
    delta = end_date - start_date
    random_days = random.randint(0, delta.days)
    return start_date + datetime.timedelta(days=random_days)

# Generate and insert records
for i in range(1, 501):
    uid = f"ABC{i:03d}"
    username = random_username()
    innvoce_num = f"INV{i:08d}"
    date = random_date()
    amount = round(random.uniform(100, 10000), 2)

    patient_data_sql = f"""
        INSERT INTO patient_data (uid, username, innvoce_num, date, amount)
        VALUES ('{uid}', '{username}', '{innvoce_num}', '{date}', {amount});
    """
    a, b = DB2Query.runQuery(patient_data_sql)
    if not a:
        print("ERROR inserting into patient_data:", b)
        break

    register_sql = f"""
        INSERT INTO register (uid, innvoce_num, paid_amt)
        VALUES ('{uid}', '{innvoce_num}', 0);
    """
    a, b = DB2Query.runQuery(register_sql)
    if not a:
        print("ERROR inserting into register:", b)
        break
    print(f"Inserted record {i}")
print("Data generation and insertion completed.")
