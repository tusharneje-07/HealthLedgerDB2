import random
import datetime
import DB2.DB2Query as DB2Query

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

# Function to generate email from name
def generate_email(name):
    # Convert name to lowercase and replace spaces with dots
    email_name = name.lower().replace(" ", ".")
    # Add random domain
    domains = ["gmail.com", "yahoo.com", "outlook.com", "healthledger.com", "email.com"]
    return f"{email_name}@{random.choice(domains)}"

# Function to get the starting UID number
def get_starting_uid_number():
    query = "SELECT MAX(UID) FROM AUTHENTICATION"
    success, result = DB2Query.runSelectQuery(query)
    if success and result and len(result) > 0:
        max_uid = result[0].get('1')  # DB2 returns column as '1' when using MAX
        if max_uid:
            try:
                number = int(max_uid[3:])  # Get number after 'ABC'
                return number + 1
            except:
                return 1
    return 1

# Get starting UID number to avoid duplicates
starting_number = get_starting_uid_number()
print(f"Starting from UID number: {starting_number}")

# Generate and insert records
for i in range(starting_number, starting_number + 500):
    uid = f"ABC{i:03d}"
    username = random_username()
    email = generate_email(username)
    password = "123"
    invoice_num = f"INV{i:08d}"
    date = random_date()
    amount = round(random.uniform(100, 10000), 0)

    # Insert into AUTHENTICATION table
    authentication_sql = f"""
        INSERT INTO AUTHENTICATION (UID, NAME, EMAIL, PASSWORD, FLAG, KEY)
        VALUES ('{uid}', '{username}', '{email}', '{password}', 'P', NULL);
    """
    print(authentication_sql)
    # a, b = DB2Query.runQuery(authentication_sql)
    if not a:
        print("ERROR inserting into AUTHENTICATION:", b)
        break

    patient_data_sql = f"""
        INSERT INTO patient_data (uid, username, innvoce_num, date, amount)
        VALUES ('{uid}', '{username}', '{invoice_num}', '{date}', {amount});
    """
    # a, b = DB2Query.runQuery(patient_data_sql)
    if not a:
        print("ERROR inserting into patient_data:", b)
        break

    register_sql = f"""
        INSERT INTO register (uid, innvoce_num, paid_amt)
        VALUES ('{uid}', '{invoice_num}', 0);
    """
    # a, b = DB2Query.runQuery(register_sql)
    if not a:
        print("ERROR inserting into register:", b)
        break

    print(f"Inserted record {i}")

print(f"Data generation and insertion completed. Total records inserted: 500")
