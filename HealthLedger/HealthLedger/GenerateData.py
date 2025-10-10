import random
import datetime
import HealthLedger.HealthLedger.DB2.DB2Query as DB2Query

# Lists of 50 Indian first and last names
first_names = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Ananya", "Diya", "Isha", "Aisha",
    "Rohan", "Kabir", "Aryan", "Anika", "Saanvi", "Krishna", "Lakshya", "Meera", "Riya", "Shreya",
    "Tanvi", "Vishal", "Neha", "Amit", "Sneha", "Kavya", "Raj", "Pooja", "Ansh", "Siddharth",
    "Ishaan", "Naina", "Devansh", "Tanish", "Priya", "Arnav", "Reyansh", "Kriti", "Harsh", "Aarohi",
    "Yash", "Mihir", "Anvi", "Shivansh", "Ritika", "Pranav", "Sanya", "Karan", "Ira", "Manya"
]

last_names = [
    "Sharma", "Patel", "Singh", "Gupta", "Mehta", "Kumar", "Reddy", "Iyer", "Chopra", "Kapoor",
    "Desai", "Jain", "Nair", "Malhotra", "Bhat", "Joshi", "Aggarwal", "Rao", "Verma", "Choudhary",
    "Pandey", "Agarwal", "Ghosh", "Shah", "Trivedi", "Mukherjee", "Saxena", "Prasad", "Naidu", "Khan",
    "Tiwari", "Dutta", "Bansal", "Singhania", "Menon", "Rathore", "Bhardwaj", "Chatterjee", "Ranganathan", "Nambiar",
    "Yadav", "Sinha", "Bhattacharya", "Kohli", "Rajput", "Ramakrishnan", "Chakraborty", "Saxena", "Shinde", "Garg"
]

# Function to generate random Indian name
def random_username():
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
    invoice_num = f"INV{i:08d}"
    date = random_date()
    amount = round(random.uniform(100, 10000), 2)

    patient_data_sql = f"""
        INSERT INTO patient_data (uid, username, innvoce_num, date, amount)
        VALUES ('{uid}', '{username}', '{invoice_num}', '{date}', {amount});
    """
    a, b = DB2Query.runQuery(patient_data_sql)
    if not a:
        print("ERROR inserting into patient_data:", b)
        break

    register_sql = f"""
        INSERT INTO register (uid, innvoce_num, paid_amt)
        VALUES ('{uid}', '{invoice_num}', 0);
    """
    a, b = DB2Query.runQuery(register_sql)
    if not a:
        print("ERROR inserting into register:", b)
        break

    print(f"Inserted record {i}")

print("Data generation and insertion completed.")
