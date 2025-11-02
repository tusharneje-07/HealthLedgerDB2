# Complete DB2 SQL Queries Explanation

This document explains **every unique SQL query** found in your Python code in **simple English**. Each query is explained word-by-word so you can understand what it does.

---

## Table of Contents
1. [SELECT Queries (35 queries)](#select-queries)
2. [INSERT Queries (2 queries)](#insert-queries)
3. [UPDATE Queries (1 query)](#update-queries)

---

## SELECT Queries

SELECT queries are used to **fetch/retrieve data** from database tables.

### Query 1: View All Invoices with Payment Details

```sql
SELECT
    p.REC_NUMBER,
    p.UID,
    p.USERNAME,
    p.INNVOCE_NUM,
    p.DATE,
    p.AMOUNT,
    CASE
        WHEN COALESCE(il.TOTAL_PAID, 0) > 0 THEN il.TOTAL_PAID
        ELSE COALESCE(r.PAID_AMT, 0)
    END AS PAID_AMOUNT
FROM patient_data p
LEFT JOIN register r
    ON p.UID = r.UID
    AND p.INNVOCE_NUM = r.INNVOCE_NUM
LEFT JOIN (
    SELECT INVOICE_NUMBER, COALESCE(SUM(PAID_AMOUNT_ON_DATE), 0) AS TOTAL_PAID
    FROM INVOICE_LOGS
    GROUP BY INVOICE_NUMBER
) il
    ON p.INNVOCE_NUM = il.INVOICE_NUMBER
ORDER BY p.DATE DESC
```

**Explanation:**

- **SELECT**: Get/fetch these columns
- **p.REC_NUMBER**: Record number from patient_data table (p is alias/short name)
- **p.UID**: User ID of the patient
- **p.USERNAME**: Name of the patient
- **p.INNVOCE_NUM**: Invoice number
- **p.DATE**: Date when invoice was created
- **p.AMOUNT**: Total amount of the invoice
- **CASE WHEN ... THEN ... ELSE ... END**: This is a condition check (like IF-ELSE)
  - **COALESCE(il.TOTAL_PAID, 0)**: If TOTAL_PAID is null (empty), use 0 instead
  - **WHEN COALESCE(il.TOTAL_PAID, 0) > 0**: If total paid from logs is greater than 0
  - **THEN il.TOTAL_PAID**: Use the total paid from invoice logs
  - **ELSE COALESCE(r.PAID_AMT, 0)**: Otherwise, use paid amount from register table
  - **AS PAID_AMOUNT**: Name this calculated column as PAID_AMOUNT
- **FROM patient_data p**: Get data from patient_data table, call it "p" for short
- **LEFT JOIN register r**: Also join with register table (called "r")
  - **LEFT JOIN**: Include all records from patient_data even if no match in register
  - **ON p.UID = r.UID AND p.INNVOCE_NUM = r.INNVOCE_NUM**: Match when UID and invoice number are same
- **LEFT JOIN (subquery) il**: Join with a subquery result called "il"
  - The subquery calculates total paid amount for each invoice from INVOICE_LOGS table
  - **GROUP BY INVOICE_NUMBER**: Group all payment logs by invoice number
  - **SUM(PAID_AMOUNT_ON_DATE)**: Add up all payments made on different dates
- **ORDER BY p.DATE DESC**: Sort results by date, newest first (DESC = descending)

**What it does**: Gets all patient invoices with their payment details, showing either the sum from payment logs or the amount from register table.

---

### Query 2: Get Invoice Payment Logs

```sql
SELECT INVOICE_NUMBER, LOG_DATE, PAID_AMOUNT_ON_DATE, LOG_REMARK
FROM INVOICE_LOGS
WHERE INVOICE_NUMBER IN ({invoice_num_list})
ORDER BY LOG_DATE DESC
```

**Explanation:**

- **SELECT**: Get these columns
- **INVOICE_NUMBER**: The invoice number
- **LOG_DATE**: Date when payment was made
- **PAID_AMOUNT_ON_DATE**: Amount paid on that specific date
- **LOG_REMARK**: Notes/comments about the payment
- **FROM INVOICE_LOGS**: From the INVOICE_LOGS table
- **WHERE INVOICE_NUMBER IN ({invoice_num_list})**: Only get records where invoice number is in the provided list
  - **IN**: Means "matches any value in this list"
  - **{invoice_num_list}**: This is a placeholder that gets replaced with actual invoice numbers like ('INV001', 'INV002')
- **ORDER BY LOG_DATE DESC**: Sort by payment date, newest first

**What it does**: Gets all payment history/logs for specific invoices, showing when payments were made and how much.

---

### Query 3: User Authentication (Login)

```sql
SELECT UID, NAME, EMAIL, PASSWORD, FLAG 
FROM AUTHENTICATION 
WHERE (UID = '{username}' OR EMAIL = '{username}') 
AND FLAG = '{user_type[0].upper()}'
```

**Explanation:**

- **SELECT**: Get these columns
- **UID**: User ID
- **NAME**: User's full name
- **EMAIL**: User's email address
- **PASSWORD**: User's password (stored in database)
- **FLAG**: User type flag (like 'S' for Staff, 'P' for Patient)
- **FROM AUTHENTICATION**: From the AUTHENTICATION table
- **WHERE**: Filter conditions:
  - **(UID = '{username}' OR EMAIL = '{username}')**: Match if either UID or EMAIL equals the username entered
    - **OR**: Means either condition can be true
  - **AND FLAG = '{user_type[0].upper()}'**: AND the user type flag must match
    - **[0].upper()**: Take first character and make it uppercase
- **'{username}'** and **'{user_type}'**: These are placeholders replaced with actual values

**What it does**: Checks if a user exists with the given username/email and user type (used for login).

---

### Query 4: Patient Login

```sql
SELECT UID, NAME, PASSWORD 
FROM AUTHENTICATION 
WHERE EMAIL = '{email}' 
AND FLAG = 'P'
```

**Explanation:**

- **SELECT**: Get UID, NAME, and PASSWORD
- **FROM AUTHENTICATION**: From the authentication table
- **WHERE EMAIL = '{email}'**: Match the email address
- **AND FLAG = 'P'**: And user type is 'P' (Patient)
  - **'P'**: Single quotes mean this is a text value

**What it does**: Gets patient user details for login verification (only for patient users).

---

### Query 5: Get UID by Email

```sql
SELECT UID 
FROM AUTHENTICATION 
WHERE EMAIL = '{email_s}' 
FETCH FIRST 1 ROW ONLY
```

**Explanation:**

- **SELECT UID**: Get only the UID column
- **FROM AUTHENTICATION**: From authentication table
- **WHERE EMAIL = '{email_s}'**: Match the email address
  - **{email_s}**: Sanitized email (special characters escaped)
- **FETCH FIRST 1 ROW ONLY**: Get only the first matching record
  - This is DB2's way of saying "LIMIT 1"

**What it does**: Finds the user ID for a given email address (gets just one result).

---

### Query 6: Get User Invoices with Total Paid

```sql
SELECT 
    p.REC_NUMBER,
    p.UID,
    p.USERNAME,
    p.INNVOCE_NUM,
    p.DATE,
    p.AMOUNT,
    COALESCE(SUM(il.PAID_AMOUNT_ON_DATE), 0) AS PAID_AMOUNT
FROM patient_data p
LEFT JOIN INVOICE_LOGS il ON p.INNVOCE_NUM = il.INVOICE_NUMBER
WHERE p.UID = '{uid}'
GROUP BY p.REC_NUMBER, p.UID, p.USERNAME, p.INNVOCE_NUM, p.DATE, p.AMOUNT
ORDER BY p.DATE DESC
```

**Explanation:**

- **COALESCE(SUM(il.PAID_AMOUNT_ON_DATE), 0)**: Sum all payments, if null use 0
  - **SUM()**: Add up all values
  - **COALESCE()**: Replace null with 0
- **LEFT JOIN INVOICE_LOGS il ON p.INNVOCE_NUM = il.INVOICE_NUMBER**: Join with payment logs
- **WHERE p.UID = '{uid}'**: Only for this specific user
- **GROUP BY**: Group records that have same values for these columns
  - Needed because we're using SUM() function
  - All columns in SELECT (except aggregated ones) must be in GROUP BY

**What it does**: Gets all invoices for a specific user with their total paid amounts calculated from payment logs.

---

### Query 7: Get Invoice by UID (Single Record)

```sql
SELECT 
    p.REC_NUMBER,
    p.UID,
    p.USERNAME,
    p.INNVOCE_NUM,
    p.DATE,
    p.AMOUNT,
    COALESCE(r.PAID_AMT, 0) AS PAID_AMT
FROM patient_data p
LEFT JOIN register r
ON p.UID = r.UID AND p.INNVOCE_NUM = r.INNVOCE_NUM
WHERE p.UID = '{uid}'
FETCH FIRST 1 ROW ONLY
```

**Explanation:**

- **COALESCE(r.PAID_AMT, 0)**: Get paid amount from register, use 0 if null
- **LEFT JOIN register r**: Join with register table
- **ON p.UID = r.UID AND p.INNVOCE_NUM = r.INNVOCE_NUM**: Match on both UID and invoice number
  - **AND**: Both conditions must be true
- **WHERE p.UID = '{uid}'**: Filter by user ID
- **FETCH FIRST 1 ROW ONLY**: Get only one result

**What it does**: Gets the most recent invoice details for a specific user.

---

### Query 8: Get Invoice Details with Payment Logs

```sql
SELECT 
    p.REC_NUMBER,
    p.UID,
    p.USERNAME,
    p.INNVOCE_NUM,
    p.DATE,
    p.AMOUNT,
    COALESCE(SUM(il.PAID_AMOUNT_ON_DATE), 0) AS PAID_AMOUNT
FROM patient_data p
LEFT JOIN register r
    ON p.UID = r.UID AND p.INNVOCE_NUM = r.INNVOCE_NUM
LEFT JOIN INVOICE_LOGS il
    ON p.INNVOCE_NUM = il.INVOICE_NUMBER
WHERE p.INNVOCE_NUM = '{invoice_num}'
GROUP BY 
    p.REC_NUMBER, p.UID, p.USERNAME, 
    p.INNVOCE_NUM, p.DATE, p.AMOUNT
FETCH FIRST 1 ROW ONLY
```

**Explanation:**

- Similar to previous queries but:
- **WHERE p.INNVOCE_NUM = '{invoice_num}'**: Filter by invoice number (not UID)
- Joins both register and invoice_logs tables
- Groups results to calculate total paid amount

**What it does**: Gets complete details of a specific invoice including all payments made.

---

### Query 9: Get Payment Logs for an Invoice

```sql
SELECT LOG_DATE, PAID_AMOUNT_ON_DATE, LOG_REMARK
FROM INVOICE_LOGS
WHERE INVOICE_NUMBER = '{invoice_num}'
ORDER BY LOG_DATE DESC
```

**Explanation:**

- **SELECT**: Get payment date, amount paid, and remarks
- **WHERE INVOICE_NUMBER = '{invoice_num}'**: For this specific invoice
- **ORDER BY LOG_DATE DESC**: Newest payments first

**What it does**: Gets the complete payment history for one invoice.

---

### Query 10: Recent Activity Logs

```sql
SELECT log_name, log_desc, log_date_time 
FROM activity 
ORDER BY log_date_time DESC 
FETCH FIRST 10 ROWS ONLY
```

**Explanation:**

- **SELECT log_name, log_desc, log_date_time**: Get activity name, description, and timestamp
- **FROM activity**: From the activity log table
- **ORDER BY log_date_time DESC**: Sort by time, newest first
- **FETCH FIRST 10 ROWS ONLY**: Get only the 10 most recent activities

**What it does**: Gets the last 10 system activities/actions performed.

---

### Query 11: Dashboard Statistics

```sql
SELECT
    COUNT(*) AS TOTAL_RECORDS,
    COALESCE(SUM(p.AMOUNT), 0) AS TOTAL_REVENUE,
    COALESCE(SUM(
        CASE
            WHEN COALESCE(il.TOTAL_PAID, 0) >= p.AMOUNT THEN 0
            ELSE p.AMOUNT - COALESCE(il.TOTAL_PAID, 0)
        END
    ), 0) AS TOTAL_PENDING_AMOUNT,
    COALESCE(SUM(
        CASE
            WHEN COALESCE(il.TOTAL_PAID, 0) >= p.AMOUNT THEN 1
            ELSE 0
        END
    ), 0) AS TOTAL_PAID_CUSTOMERS
FROM patient_data p
LEFT JOIN (
    SELECT INVOICE_NUMBER, COALESCE(SUM(PAID_AMOUNT_ON_DATE), 0) AS TOTAL_PAID
    FROM INVOICE_LOGS
    GROUP BY INVOICE_NUMBER
) il
ON p.INNVOCE_NUM = il.INVOICE_NUMBER
```

**Explanation:**

- **COUNT(*)**: Count all records (number of invoices)
  - **AS TOTAL_RECORDS**: Name this column TOTAL_RECORDS
- **COALESCE(SUM(p.AMOUNT), 0)**: Sum all invoice amounts, use 0 if null
  - **AS TOTAL_REVENUE**: Total money expected
- **CASE WHEN ... THEN ... ELSE ... END**: Conditional calculation
  - **WHEN COALESCE(il.TOTAL_PAID, 0) >= p.AMOUNT**: If fully paid
  - **THEN 0**: Pending amount is 0
  - **ELSE p.AMOUNT - COALESCE(il.TOTAL_PAID, 0)**: Otherwise, calculate remaining amount
- **SUM(CASE ... END)**: Sum up all the conditional results
- **TOTAL_PAID_CUSTOMERS**: Count how many invoices are fully paid
  - Uses **THEN 1 ELSE 0**: Returns 1 if paid, 0 if not, then sums them

**What it does**: Calculates overall statistics - total invoices, total revenue, pending amounts, and paid customer count.

---

### Query 12: Count Records with Filters

```sql
SELECT COUNT(*) AS TOTAL
FROM (
    SELECT p.INNVOCE_NUM
    FROM patient_data p
    {where_clause}
    GROUP BY p.INNVOCE_NUM
) AS SUB
```

**Explanation:**

- **SELECT COUNT(*) AS TOTAL**: Count all results
- **FROM (subquery) AS SUB**: Count results from this subquery (inner query)
  - **SELECT p.INNVOCE_NUM**: Get invoice numbers
  - **{where_clause}**: Optional filter conditions (search, date range)
  - **GROUP BY p.INNVOCE_NUM**: Group by invoice number (removes duplicates)
- **AS SUB**: Name the subquery result "SUB"

**What it does**: Counts total unique invoices matching the search/filter criteria.

---

### Query 13: Load Paginated Invoice Data with Filters

```sql
WITH InvoiceData AS (
    SELECT 
        p.REC_NUMBER, 
        p.UID, 
        p.USERNAME, 
        p.INNVOCE_NUM, 
        p.DATE, 
        p.AMOUNT,
        COALESCE(SUM(il.PAID_AMOUNT_ON_DATE), 0) AS PAID_AMOUNT
    FROM patient_data p
    LEFT JOIN INVOICE_LOGS il ON p.INNVOCE_NUM = il.INVOICE_NUMBER
    {where_clause}
    GROUP BY 
        p.REC_NUMBER, p.UID, p.USERNAME, 
        p.INNVOCE_NUM, p.DATE, p.AMOUNT
)
SELECT * FROM InvoiceData
{status_filter}
ORDER BY DATE DESC
OFFSET {offset} ROWS
FETCH FIRST {size} ROWS ONLY
```

**Explanation:**

- **WITH InvoiceData AS (...)**: Create a temporary result set called "InvoiceData"
  - **WITH**: This is called a Common Table Expression (CTE)
  - Like creating a temporary table that exists only for this query
- **{where_clause}**: Optional filters (search by name, UID, invoice number, date range)
- **{status_filter}**: Optional filter (paid or pending status)
- **ORDER BY DATE DESC**: Sort by date, newest first
- **OFFSET {offset} ROWS**: Skip this many rows
  - Used for pagination (like page 2 starts after skipping first 10)
- **FETCH FIRST {size} ROWS ONLY**: Get only this many rows
  - Like "show 10 records per page"

**What it does**: Gets a page of invoice records with search/filter capabilities (for displaying in tables with pagination).

---

### Query 14: User Dashboard Statistics

```sql
WITH il AS (
    SELECT INVOICE_NUMBER, COALESCE(SUM(PAID_AMOUNT_ON_DATE), 0) AS TOTAL_PAID
    FROM INVOICE_LOGS
    GROUP BY INVOICE_NUMBER
)
SELECT
    COUNT(*) AS TOTAL_INVOICES,
    COALESCE(SUM(p.AMOUNT), 0) AS TOTAL_AMOUNT,
    COALESCE(SUM(
        CASE WHEN COALESCE(il.TOTAL_PAID,0) < p.AMOUNT 
        THEN p.AMOUNT - COALESCE(il.TOTAL_PAID,0) 
        ELSE 0 END
    ), 0) AS PENDING_DUES,
    COALESCE(SUM(CASE WHEN COALESCE(il.TOTAL_PAID,0) = 0 THEN 1 ELSE 0 END), 0) AS UNPAID_COUNT,
    COALESCE(SUM(CASE WHEN COALESCE(il.TOTAL_PAID,0) >= p.AMOUNT 
        THEN COALESCE(p.AMOUNT,0) 
        ELSE COALESCE(il.TOTAL_PAID,0) END), 0) AS PAID_AMOUNT,
    COALESCE(SUM(CASE WHEN COALESCE(il.TOTAL_PAID,0) >= p.AMOUNT THEN 1 ELSE 0 END), 0) AS PAID_COUNT,
    COALESCE(SUM(CASE WHEN COALESCE(il.TOTAL_PAID,0) > 0 
        AND COALESCE(il.TOTAL_PAID,0) < p.AMOUNT THEN 1 ELSE 0 END), 0) AS PENDING_COUNT
FROM patient_data p
LEFT JOIN il ON p.INNVOCE_NUM = il.INVOICE_NUMBER
WHERE p.UID = '{uid}'
```

**Explanation:**

- **WITH il AS (...)**: First, create a temporary table with total paid amounts per invoice
- **COUNT(*) AS TOTAL_INVOICES**: Count of all invoices for this user
- **PENDING_DUES**: Sum of all remaining amounts (amount - paid)
  - **CASE WHEN COALESCE(il.TOTAL_PAID,0) < p.AMOUNT**: If not fully paid
  - **THEN p.AMOUNT - COALESCE(il.TOTAL_PAID,0)**: Calculate remaining
  - **ELSE 0**: If fully paid, pending is 0
- **UNPAID_COUNT**: Count invoices with zero payment
  - **CASE WHEN COALESCE(il.TOTAL_PAID,0) = 0 THEN 1 ELSE 0**: Returns 1 if unpaid
  - **SUM(...)**: Adds up all the 1s to get count
- **PAID_AMOUNT**: Total money actually paid
- **PAID_COUNT**: Number of fully paid invoices
- **PENDING_COUNT**: Number of partially paid invoices
  - **COALESCE(il.TOTAL_PAID,0) > 0**: Has some payment
  - **AND COALESCE(il.TOTAL_PAID,0) < p.AMOUNT**: But not fully paid

**What it does**: Calculates comprehensive statistics for a specific user's invoices (for patient dashboard).

---

### Query 15: Monthly Payment Summary

```sql
WITH user_invoices AS (
    SELECT INNVOCE_NUM FROM patient_data WHERE UID = '{uid}'
)
SELECT
    COALESCE(SUM(CASE WHEN MONTH(LOG_DATE) = {this_month} 
        AND YEAR(LOG_DATE) = {this_year} 
        THEN PAID_AMOUNT_ON_DATE ELSE 0 END), 0) AS THIS_MONTH,
    COALESCE(SUM(CASE WHEN MONTH(LOG_DATE) = {last_month} 
        AND YEAR(LOG_DATE) = {last_month_year} 
        THEN PAID_AMOUNT_ON_DATE ELSE 0 END), 0) AS LAST_MONTH
FROM INVOICE_LOGS il
JOIN user_invoices ui ON ui.INNVOCE_NUM = il.INVOICE_NUMBER
```

**Explanation:**

- **WITH user_invoices AS (...)**: First, get all invoice numbers for this user
- **MONTH(LOG_DATE)**: Extract month number from date (1-12)
  - **MONTH()**: DB2 function to get month
- **YEAR(LOG_DATE)**: Extract year from date (e.g., 2025)
- **CASE WHEN MONTH(LOG_DATE) = {this_month} AND YEAR(LOG_DATE) = {this_year}**: If payment is from current month/year
- **THEN PAID_AMOUNT_ON_DATE ELSE 0**: Use the payment amount, otherwise 0
- **SUM(CASE ...)**: Sum all payments from current month
- **THIS_MONTH**: Total paid this month
- **LAST_MONTH**: Total paid last month (similar logic)
- **JOIN user_invoices ui**: Only include payments for this user's invoices

**What it does**: Calculates how much the user paid this month vs last month (for showing payment trends).

---

### Query 16: Recent User Transactions

```sql
WITH user_invoices AS (
    SELECT INNVOCE_NUM, AMOUNT FROM patient_data WHERE UID = '{uid}'
),
total_paid AS (
    SELECT INVOICE_NUMBER, COALESCE(SUM(PAID_AMOUNT_ON_DATE),0) AS TOTAL_PAID
    FROM INVOICE_LOGS
    WHERE INVOICE_NUMBER IN (SELECT INNVOCE_NUM FROM user_invoices)
    GROUP BY INVOICE_NUMBER
)
SELECT il.INVOICE_NUMBER, il.LOG_DATE, il.PAID_AMOUNT_ON_DATE, 
       COALESCE(tp.TOTAL_PAID,0) AS TOTAL_PAID, ui.AMOUNT
FROM INVOICE_LOGS il
JOIN user_invoices ui ON ui.INNVOCE_NUM = il.INVOICE_NUMBER
LEFT JOIN total_paid tp ON tp.INVOICE_NUMBER = il.INVOICE_NUMBER
ORDER BY il.LOG_DATE DESC
FETCH FIRST 5 ROWS ONLY
```

**Explanation:**

- **WITH user_invoices AS (...)**: Get user's invoices
- **WITH total_paid AS (...)**: Calculate total paid for each invoice
  - **WHERE INVOICE_NUMBER IN (SELECT ...)**: Only for this user's invoices
    - **IN (SELECT ...)**: Subquery returns list of invoice numbers
- **SELECT**: Get invoice number, payment date, amount paid, total paid, and invoice amount
- **JOIN user_invoices ui**: Match with user's invoices
- **LEFT JOIN total_paid tp**: Get total paid amount
- **ORDER BY il.LOG_DATE DESC**: Sort by payment date, newest first
- **FETCH FIRST 5 ROWS ONLY**: Get only last 5 transactions

**What it does**: Gets the 5 most recent payment transactions for a user (for recent activity section).

---

### Query 17: Total Revenue

```sql
SELECT COALESCE(SUM(AMOUNT), 0) AS TOTAL_REVENUE
FROM PATIENT_DATA
```

**Explanation:**

- **SUM(AMOUNT)**: Add up all invoice amounts
- **COALESCE(..., 0)**: If result is null, use 0
- **AS TOTAL_REVENUE**: Name the result column
- **FROM PATIENT_DATA**: From patient data table

**What it does**: Calculates total expected revenue from all invoices.

---

### Query 18: Total Collected Payments

```sql
SELECT COALESCE(SUM(PAID_AMOUNT_ON_DATE), 0) AS TOTAL_COLLECTED
FROM INVOICE_LOGS
```

**Explanation:**

- **SUM(PAID_AMOUNT_ON_DATE)**: Add up all payments made
- **FROM INVOICE_LOGS**: From payment logs table

**What it does**: Calculates total money actually collected from all payments.

---

### Query 19: Outstanding Balance

```sql
SELECT COALESCE(SUM(p.AMOUNT) - SUM(COALESCE(il.TOTAL_PAID, 0)), 0) AS OUTSTANDING
FROM PATIENT_DATA p
LEFT JOIN (
    SELECT INVOICE_NUMBER, SUM(PAID_AMOUNT_ON_DATE) AS TOTAL_PAID
    FROM INVOICE_LOGS
    GROUP BY INVOICE_NUMBER
) il ON p.INNVOCE_NUM = il.INVOICE_NUMBER
```

**Explanation:**

- **SUM(p.AMOUNT)**: Sum of all invoice amounts
- **SUM(COALESCE(il.TOTAL_PAID, 0))**: Sum of all paid amounts
- **SUM(p.AMOUNT) - SUM(COALESCE(il.TOTAL_PAID, 0))**: Total expected minus total paid = outstanding
- The subquery first groups payments by invoice
- **AS OUTSTANDING**: Name this result

**What it does**: Calculates total outstanding (unpaid) balance across all invoices.

---

### Query 20: Monthly Revenue Trend

```sql
SELECT 
    SUBSTR(CHAR(LOG_DATE), 1, 7) AS MONTH,
    COALESCE(SUM(PAID_AMOUNT_ON_DATE), 0) AS REVENUE
FROM INVOICE_LOGS
WHERE LOG_DATE >= CURRENT_DATE - 12 MONTHS
GROUP BY SUBSTR(CHAR(LOG_DATE), 1, 7)
ORDER BY MONTH ASC
```

**Explanation:**

- **SUBSTR(CHAR(LOG_DATE), 1, 7)**: Extract year-month from date
  - **CHAR(LOG_DATE)**: Convert date to string (like "2025-11-02")
  - **SUBSTR(..., 1, 7)**: Get first 7 characters (like "2025-11")
  - **AS MONTH**: Name this column MONTH
- **WHERE LOG_DATE >= CURRENT_DATE - 12 MONTHS**: Only last 12 months
  - **CURRENT_DATE**: Today's date
  - **- 12 MONTHS**: Subtract 12 months
  - **>=**: Greater than or equal to
- **GROUP BY SUBSTR(...)**: Group payments by month
- **ORDER BY MONTH ASC**: Sort by month, oldest to newest
  - **ASC**: Ascending order

**What it does**: Gets monthly payment totals for the last 12 months (for trend charts).

---

### Query 21: Total Patients Count

```sql
SELECT COUNT(DISTINCT UID) AS TOTAL_PATIENTS
FROM PATIENT_DATA
```

**Explanation:**

- **COUNT(DISTINCT UID)**: Count unique UIDs
  - **DISTINCT**: Remove duplicates (each UID counted only once)
  - **COUNT()**: Count the number
- **AS TOTAL_PATIENTS**: Name the result

**What it does**: Counts total number of unique patients in the system.

---

### Query 22: Average Invoice Amount

```sql
SELECT COALESCE(AVG(AMOUNT), 0) AS AVG_SPENDING
FROM PATIENT_DATA
```

**Explanation:**

- **AVG(AMOUNT)**: Calculate average of all amounts
  - **AVG()**: Average function (sum / count)
- **COALESCE(..., 0)**: Use 0 if null
- **AS AVG_SPENDING**: Name the result

**What it does**: Calculates average invoice amount per patient.

---

### Query 23: Repeat Patients Count

```sql
SELECT COUNT(*) AS REPEAT_PATIENTS
FROM (
    SELECT UID
    FROM PATIENT_DATA
    GROUP BY UID
    HAVING COUNT(*) > 1
) AS repeat
```

**Explanation:**

- **GROUP BY UID**: Group records by user ID
- **HAVING COUNT(*) > 1**: Keep only groups with more than 1 record
  - **HAVING**: Filter after grouping (WHERE filters before grouping)
  - **COUNT(*) > 1**: More than one invoice
- **SELECT UID FROM (subquery)**: Get UIDs from this inner query
- **COUNT(*)**: Count how many such UIDs exist
- **AS REPEAT_PATIENTS**: Name the result

**What it does**: Counts patients who have more than one invoice (repeat customers).

---

### Query 24: Top Paying Patients

```sql
SELECT 
    p.UID,
    p.USERNAME AS NAME,
    COALESCE(SUM(il.PAID_AMOUNT_ON_DATE), 0) AS TOTAL_PAID
FROM PATIENT_DATA p
LEFT JOIN INVOICE_LOGS il ON p.INNVOCE_NUM = il.INVOICE_NUMBER
GROUP BY p.UID, p.USERNAME
ORDER BY TOTAL_PAID DESC
FETCH FIRST 10 ROWS ONLY
```

**Explanation:**

- **p.USERNAME AS NAME**: Get username and rename column to NAME
- **COALESCE(SUM(il.PAID_AMOUNT_ON_DATE), 0)**: Total paid by each patient
- **GROUP BY p.UID, p.USERNAME**: Group by patient (one row per patient)
- **ORDER BY TOTAL_PAID DESC**: Sort by payment amount, highest first
- **FETCH FIRST 10 ROWS ONLY**: Get top 10 only

**What it does**: Gets the top 10 patients who have paid the most money.

---

### Query 25: Invoice Volume Trend

```sql
SELECT 
    SUBSTR(CHAR(DATE), 1, 7) AS MONTH,
    COUNT(*) AS COUNT
FROM PATIENT_DATA
WHERE DATE >= CURRENT_DATE - 12 MONTHS
GROUP BY SUBSTR(CHAR(DATE), 1, 7)
ORDER BY MONTH ASC
```

**Explanation:**

- Similar to monthly revenue trend but:
- **COUNT(*)**: Count number of invoices (not sum of amounts)
- **FROM PATIENT_DATA**: From patient data (not payment logs)

**What it does**: Shows how many invoices were created each month for the last 12 months.

---

### Query 26: Payment Mode Distribution

```sql
SELECT 
    COALESCE(PAYMENT_MODE, 'UNKNOWN') AS MODE,
    COUNT(*) AS COUNT,
    COALESCE(SUM(PAID_AMOUNT_ON_DATE), 0) AS AMOUNT
FROM INVOICE_LOGS
WHERE PAYMENT_MODE IS NOT NULL
GROUP BY PAYMENT_MODE
ORDER BY AMOUNT DESC
```

**Explanation:**

- **COALESCE(PAYMENT_MODE, 'UNKNOWN')**: If payment mode is null, show 'UNKNOWN'
- **COUNT(*)**: Count number of transactions per payment mode
- **SUM(PAID_AMOUNT_ON_DATE)**: Total amount paid via each mode
- **WHERE PAYMENT_MODE IS NOT NULL**: Exclude null payment modes
  - **IS NOT NULL**: Is not empty/null
- **GROUP BY PAYMENT_MODE**: Group by each payment method (CASH, CARD, RAZORPAY, etc.)
- **ORDER BY AMOUNT DESC**: Sort by amount, highest first

**What it does**: Shows breakdown of payments by method (cash, card, online) with counts and totals.

---

### Query 27: All Patients List with Payment Status

```sql
SELECT 
    p.REC_NUMBER,
    p.UID,
    p.USERNAME,
    p.INNVOCE_NUM,
    p.DATE,
    p.AMOUNT,
    COALESCE(SUM(il.PAID_AMOUNT_ON_DATE), 0) AS PAID_AMOUNT
FROM PATIENT_DATA p
LEFT JOIN INVOICE_LOGS il ON p.INNVOCE_NUM = il.INVOICE_NUMBER
GROUP BY p.REC_NUMBER, p.UID, p.USERNAME, p.INNVOCE_NUM, p.DATE, p.AMOUNT
ORDER BY p.DATE DESC
```

**Explanation:**

- Gets complete list of all patients with their invoices
- Calculates paid amount for each invoice
- **GROUP BY**: Ensures one row per invoice
- **ORDER BY p.DATE DESC**: Newest invoices first

**What it does**: Lists all patients and their invoices with payment status (for patient list view).

---

### Query 28: Invoice Count Query

```sql
SELECT COUNT(DISTINCT INNVOCE_NUM) AS TOTAL_INVOICES
FROM PATIENT_DATA
```

**Explanation:**

- **COUNT(DISTINCT INNVOCE_NUM)**: Count unique invoice numbers
- **FROM PATIENT_DATA**: From patient data table

**What it does**: Counts total number of unique invoices in the system.

---

### Query 29: Average Payment Amount

```sql
SELECT COALESCE(AVG(PAID_AMOUNT_ON_DATE), 0) AS AVG_PAYMENT
FROM INVOICE_LOGS
```

**Explanation:**

- **AVG(PAID_AMOUNT_ON_DATE)**: Average payment amount per transaction
- **FROM INVOICE_LOGS**: From payment logs

**What it does**: Calculates average payment amount per transaction.

---

### Query 30: Activity Log Count

```sql
SELECT 
    LOG_DATE_TIME,
    LOG_NAME,
    LOG_DESC
FROM ACTIVITY
ORDER BY LOG_DATE_TIME DESC
FETCH FIRST 20 ROWS ONLY
```

**Explanation:**

- **SELECT**: Get timestamp, activity name, and description
- **FROM ACTIVITY**: From activity log table
- **ORDER BY LOG_DATE_TIME DESC**: Sort by time, newest first
- **FETCH FIRST 20 ROWS ONLY**: Get only 20 most recent activities

**What it does**: Gets last 20 system activities for activity log display.

---

### Query 31: Get All Patient Users

```sql
SELECT DISTINCT UID, NAME, EMAIL 
FROM AUTHENTICATION 
WHERE FLAG = 'P'
ORDER BY UID
```

**Explanation:**

- **SELECT DISTINCT**: Get unique records (no duplicates)
- **UID, NAME, EMAIL**: User ID, name, and email
- **WHERE FLAG = 'P'**: Only patient users (P = Patient)
- **ORDER BY UID**: Sort by user ID

**What it does**: Gets list of all patient users for dropdown/selection purposes.

---

### Query 32: Get Last Invoice Number

```sql
SELECT INNVOCE_NUM 
FROM patient_data 
ORDER BY REC_NUMBER DESC 
FETCH FIRST 1 ROW ONLY
```

**Explanation:**

- **SELECT INNVOCE_NUM**: Get invoice number
- **ORDER BY REC_NUMBER DESC**: Sort by record number, highest first
  - Record number auto-increments, so highest = most recent
- **FETCH FIRST 1 ROW ONLY**: Get only the first result

**What it does**: Gets the most recent invoice number (used to generate next invoice number).

---

### Query 33: Get User by UID

```sql
SELECT UID, NAME, EMAIL 
FROM AUTHENTICATION 
WHERE UID = '{uid}' AND FLAG = 'P'
FETCH FIRST 1 ROW ONLY
```

**Explanation:**

- **WHERE UID = '{uid}' AND FLAG = 'P'**: Match specific UID and is a patient
- **FETCH FIRST 1 ROW ONLY**: Get one result

**What it does**: Gets user details for a specific patient UID.

---

### Query 34: Update Authentication Key

```sql
UPDATE AUTHENTICATION 
SET KEY = '{auth_token}' 
WHERE EMAIL = '{email}'
```

**Explanation in UPDATE section below.**

---

### Query 35: Total Paid Count Query

```sql
SELECT COALESCE(SUM(CASE WHEN PAID_AMT >= AMOUNT THEN 1 ELSE 0 END), 0) 
AS PAID_COUNT
FROM patient_data p
LEFT JOIN register r ON p.UID = r.UID AND p.INNVOCE_NUM = r.INNVOCE_NUM
```

**Explanation:**

- **CASE WHEN PAID_AMT >= AMOUNT THEN 1 ELSE 0**: If fully paid, return 1, else 0
- **SUM(CASE ...)**: Add up all the 1s to get count
- **AS PAID_COUNT**: Name the result

**What it does**: Counts how many invoices are fully paid.

---

## INSERT Queries

INSERT queries are used to **add new records** to database tables.

### Query 1: Insert Activity Log

```sql
INSERT INTO activity (log_name, log_desc, log_date_time) 
VALUES ('Payment Update', '{log_desc}', '{current_timestamp}')
```

**Explanation:**

- **INSERT INTO activity**: Add a new record to the activity table
- **(log_name, log_desc, log_date_time)**: These are the column names
- **VALUES**: The values to insert
- **'Payment Update'**: Activity name (in quotes = text)
- **'{log_desc}'**: Activity description (placeholder for actual description)
- **'{current_timestamp}'**: Current date and time (placeholder for actual timestamp)

**What it does**: Adds a new activity log entry when a payment is updated.

---

### Query 2: Insert Invoice Payment Log

```sql
INSERT INTO INVOICE_LOGS 
(INVOICE_NUMBER, UID, LOG_DATE, AMOUNT, PAID_AMOUNT_ON_DATE, 
REMAINING_AMOUNT_ON_DATE, LOG_REMARK, PAYMENT_MODE, PAYMENT_ID) 
VALUES ('{invoice_num}', '{uid}', '{current_timestamp}', 
{total_amount}, {paid_amount}, {remaining_amount}, '{log_remark}', 
'{payment_mode}', '{payment_id}')
```

**Explanation:**

- **INSERT INTO INVOICE_LOGS**: Add record to invoice logs table
- Column names:
  - **INVOICE_NUMBER**: Invoice number
  - **UID**: User ID
  - **LOG_DATE**: Date of payment
  - **AMOUNT**: Total invoice amount
  - **PAID_AMOUNT_ON_DATE**: Amount paid on this date
  - **REMAINING_AMOUNT_ON_DATE**: Amount still pending
  - **LOG_REMARK**: Notes about this payment
  - **PAYMENT_MODE**: Payment method (CASH, CARD, RAZORPAY, etc.)
  - **PAYMENT_ID**: Payment transaction ID
- **VALUES (...)**: Actual values to insert
  - Values in quotes are text
  - Values without quotes are numbers

**What it does**: Records a payment transaction with all details in the payment log.

---

### Query 3: Insert Patient Data

```sql
INSERT INTO patient_data (uid, username, innvoce_num, date, amount)
VALUES ('{uid}', '{username}', '{innvoce_num}', '{date}', {amount})
```

**Explanation:**

- **INSERT INTO patient_data**: Add new record to patient data table
- Columns: uid, username, invoice number, date, amount
- **VALUES**: The actual data to insert

**What it does**: Creates a new patient invoice record.

---

### Query 4: Insert into Register

```sql
INSERT INTO register (uid, innvoce_num, paid_amt)
VALUES ('{uid}', '{innvoce_num}', 0)
```

**Explanation:**

- **INSERT INTO register**: Add record to register table
- **paid_amt**: Initially set to 0 (no payment yet)

**What it does**: Creates a register entry for new invoice with zero paid amount.

---

## UPDATE Queries

UPDATE queries are used to **modify existing records** in database tables.

### Query 1: Update Payment Amount

```sql
UPDATE register 
SET PAID_AMT = {paid_amount} 
WHERE UID = '{uid}' AND INNVOCE_NUM = '{invoice_num}'
```

**Explanation:**

- **UPDATE register**: Modify the register table
- **SET PAID_AMT = {paid_amount}**: Change the paid amount column to this new value
  - **SET**: Specify what to change
- **WHERE UID = '{uid}' AND INNVOCE_NUM = '{invoice_num}'**: Only update this specific record
  - **WHERE**: Filter which rows to update
  - **AND**: Both conditions must match
  - Without WHERE, ALL rows would be updated!

**What it does**: Updates the paid amount for a specific invoice in the register table.

---

### Query 2: Update Authentication Key

```sql
UPDATE AUTHENTICATION 
SET KEY = '{auth_token}' 
WHERE EMAIL = '{email}'
```

**Explanation:**

- **UPDATE AUTHENTICATION**: Modify authentication table
- **SET KEY = '{auth_token}'**: Update the KEY column with new authentication token
- **WHERE EMAIL = '{email}'**: Only for this email address

**What it does**: Stores the authentication token for a user (used for session management).

---

## Common DB2 Keywords and Terms

### Data Types & Functions
- **COALESCE(value, default)**: If value is null, use default instead
- **SUM(column)**: Add up all values in that column
- **COUNT(*)**: Count number of rows
- **AVG(column)**: Calculate average
- **DISTINCT**: Remove duplicate values
- **SUBSTR(string, start, length)**: Extract part of a string
- **CHAR(value)**: Convert to string
- **MONTH(date)**: Extract month number from date
- **YEAR(date)**: Extract year from date
- **CURRENT_DATE**: Today's date

### Query Structure
- **SELECT**: Get/fetch data
- **FROM**: Which table to get data from
- **WHERE**: Filter rows (conditions)
- **GROUP BY**: Group rows that have same values
- **HAVING**: Filter after grouping
- **ORDER BY**: Sort results
- **ASC**: Ascending order (low to high, A to Z)
- **DESC**: Descending order (high to low, Z to A)
- **FETCH FIRST n ROWS ONLY**: Get only first n results (like LIMIT in MySQL)
- **OFFSET n ROWS**: Skip first n rows

### Join Types
- **LEFT JOIN**: Include all from left table, matching from right table
- **JOIN** (or INNER JOIN): Only include matching rows from both tables
- **ON**: Condition for joining tables

### Conditions & Logic
- **CASE WHEN condition THEN value ELSE other_value END**: If-else logic in SQL
- **AND**: Both conditions must be true
- **OR**: Either condition can be true
- **IN (list)**: Value matches any in the list
- **IS NULL**: Value is empty/null
- **IS NOT NULL**: Value is not empty
- **=**: Equals
- **>**: Greater than
- **<**: Less than
- **>=**: Greater than or equal
- **<=**: Less than or equal

### Advanced Concepts
- **WITH ... AS (...)**: Create temporary result set (Common Table Expression)
- **AS**: Rename column or table (alias)
- **Subquery**: Query inside another query (in parentheses)

---

## Tables in Your Database

1. **patient_data**: Main table with patient invoices
   - REC_NUMBER, UID, USERNAME, INNVOCE_NUM, DATE, AMOUNT

2. **AUTHENTICATION**: User login credentials
   - UID, NAME, EMAIL, PASSWORD, FLAG, KEY

3. **register**: Payment registration
   - UID, INNVOCE_NUM, PAID_AMT

4. **INVOICE_LOGS**: Payment transaction history
   - INVOICE_NUMBER, UID, LOG_DATE, AMOUNT, PAID_AMOUNT_ON_DATE, REMAINING_AMOUNT_ON_DATE, LOG_REMARK, PAYMENT_MODE, PAYMENT_ID

5. **activity**: System activity logs
   - LOG_NAME, LOG_DESC, LOG_DATE_TIME

---
