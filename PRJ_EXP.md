# HealthLedger - Comprehensive Project Documentation

## 📋 Table of Contents
1. [Executive Summary](#executive-summary)
2. [Project Overview](#project-overview)
3. [Technical Architecture](#technical-architecture)
4. [Database Design](#database-design)
5. [System Features](#system-features)
6. [Technology Stack](#technology-stack)
7. [Implementation Details](#implementation-details)
8. [API Documentation](#api-documentation)
9. [Security Features](#security-features)
10. [Deployment Guide](#deployment-guide)
11. [User Workflows](#user-workflows)
12. [Future Enhancements](#future-enhancements)

---

## 📊 Executive Summary

**HealthLedger** is a comprehensive Hospital Billing and Patient Management System built with Django and IBM DB2. The system provides a robust platform for healthcare facilities to manage patient records, invoices, payments, and analytics with real-time insights powered by AI.

### Key Highlights
- **Full-Stack Web Application**: Django-based backend with responsive frontend
- **Enterprise Database**: IBM DB2 integration for high-performance data management
- **Dual-User System**: Separate portals for management staff and patients
- **Payment Integration**: Razorpay payment gateway for online transactions
- **AI-Powered Analytics**: GROQ AI integration for intelligent business insights
- **Comprehensive Reporting**: PDF generation with charts and analytics
- **Email Services**: Resend API for OTP-based password recovery

---

## 🎯 Project Overview

### Problem Statement
Healthcare facilities need an efficient system to:
- Manage patient records and medical invoices
- Track payments with detailed transaction history
- Provide patients with self-service access to their billing information
- Generate analytics and reports for business intelligence
- Ensure secure authentication and data privacy

### Solution
HealthLedger provides a centralized platform that:
- Streamlines invoice creation and payment tracking
- Enables patient self-service through a dedicated portal
- Offers real-time analytics and AI-powered insights
- Supports multiple payment modes (Cash, Card, Online)
- Maintains comprehensive audit trails of all activities

### Target Users
1. **Hospital Management Staff**: Create invoices, manage payments, view analytics
2. **Patients**: View invoices, make payments, track payment history
3. **System Administrators**: User registration, system configuration

---

## 🏗️ Technical Architecture

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       Client Layer                          │
│  ┌──────────────────┐            ┌──────────────────┐      │
│  │  Management UI   │            │   Patient UI     │      │
│  │  (Staff Portal)  │            │  (User Portal)   │      │
│  └──────────────────┘            └──────────────────┘      │
└─────────────────────────────────────────────────────────────┘
                          │
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                        │
│                  Django Web Framework                       │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐           │
│  │   Views    │  │    URLs    │  │  Templates │           │
│  └────────────┘  └────────────┘  └────────────┘           │
└─────────────────────────────────────────────────────────────┘
                          │
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                   Integration Layer                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ DB2 Query│  │ Razorpay │  │ Resend   │  │   GROQ   │  │
│  │  Module  │  │ Payment  │  │  Email   │  │    AI    │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
└─────────────────────────────────────────────────────────────┘
                          │
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                     Data Layer                              │
│              IBM DB2 Database (HOSPITAL)                    │
│  Schema: NEJET                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │patient_data  │  │ INVOICE_LOGS │  │AUTHENTICATION│     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│  ┌──────────────┐  ┌──────────────┐                       │
│  │  register    │  │   activity   │                       │
│  └──────────────┘  └──────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

### Project Structure

```
HealthLedger/
├── HealthLedger/                  # Django Project Directory
│   ├── __init__.py
│   ├── settings.py                # Django Configuration
│   ├── urls.py                    # URL Routing
│   ├── views.py                   # View Functions (3000+ lines)
│   ├── wsgi.py                    # WSGI Configuration
│   ├── asgi.py                    # ASGI Configuration
│   ├── GenerateData.py            # Sample Data Generator
│   └── DB2/
│       └── DB2Query.py            # DB2 Database Interface
├── templates/                     # Frontend Templates
│   ├── package.json               # NPM Dependencies
│   ├── tailwind.config.js         # Tailwind CSS Config
│   └── src/
│       ├── css/                   # Stylesheets
│       ├── images/                # Static Images
│       ├── management/            # Management Portal HTML
│       │   ├── DASH.html
│       │   ├── CREATE.html
│       │   ├── UPDATE.html
│       │   ├── VIEW_ALL.html
│       │   ├── PRINT_INVOICE.html
│       │   ├── ANALYTICS.html
│       │   ├── LOGIN.html
│       │   ├── REGISTER.html
│       │   ├── LOGOUT.html
│       │   └── RAZORPAY_PAYMENT.html
│       └── user/                  # Patient Portal HTML
│           ├── DASH.html
│           ├── INVOICES.html
│           └── RESET.html
├── db.sqlite3                     # Django Internal DB (not used for data)
├── manage.py                      # Django Management Script
├── .env                          # Environment Variables
├── DB2QueryServer.py             # Standalone DB2 API Server
└── DB2Q.md                       # DB2 Query Documentation
```

---

## 🗄️ Database Design

### Database Information
- **DBMS**: IBM DB2
- **Database Name**: HOSPITAL
- **Schema**: NEJET
- **Connection**: TCP/IP on port 25000

### Tables Schema

#### 1. AUTHENTICATION
Stores user credentials and authentication information.

| Column   | Type          | Description                          |
|----------|---------------|--------------------------------------|
| UID      | VARCHAR       | Unique User ID (Primary Key)        |
| NAME     | VARCHAR       | User's full name                     |
| EMAIL    | VARCHAR       | Email address (Unique)               |
| PASSWORD | VARCHAR       | User password                        |
| FLAG     | CHAR(1)       | User type: 'S' (Staff) or 'P' (Patient) |
| KEY      | VARCHAR       | Session authentication key           |

#### 2. patient_data
Main table for patient invoices.

| Column      | Type          | Description                       |
|-------------|---------------|-----------------------------------|
| REC_NUMBER  | INTEGER       | Auto-increment record number (PK) |
| UID         | VARCHAR       | Patient User ID (Foreign Key)     |
| USERNAME    | VARCHAR       | Patient name                      |
| INNVOCE_NUM | VARCHAR       | Invoice number (Unique)           |
| DATE        | DATE          | Invoice creation date             |
| AMOUNT      | DECIMAL       | Total invoice amount              |

#### 3. register
Tracks payment registration for invoices.

| Column      | Type          | Description                       |
|-------------|---------------|-----------------------------------|
| UID         | VARCHAR       | Patient User ID                   |
| INNVOCE_NUM | VARCHAR       | Invoice number                    |
| PAID_AMT    | DECIMAL       | Amount paid (legacy field)        |

#### 4. INVOICE_LOGS
Detailed payment transaction history.

| Column                 | Type          | Description                    |
|------------------------|---------------|--------------------------------|
| INVOICE_NUMBER         | VARCHAR       | Related invoice number         |
| UID                    | VARCHAR       | Patient User ID                |
| LOG_DATE               | TIMESTAMP     | Payment date and time          |
| AMOUNT                 | DECIMAL       | Total invoice amount           |
| PAID_AMOUNT_ON_DATE    | DECIMAL       | Amount paid in this transaction|
| REMAINING_AMOUNT_ON_DATE| DECIMAL      | Remaining balance after payment|
| LOG_REMARK             | VARCHAR       | Payment notes/description      |
| PAYMENT_MODE           | VARCHAR       | Payment method (CASH/CARD/RAZ) |
| PAYMENT_ID             | VARCHAR       | Transaction/Payment ID         |

#### 5. activity
System activity audit log.

| Column         | Type          | Description                    |
|----------------|---------------|--------------------------------|
| LOG_NAME       | VARCHAR       | Activity name/type             |
| LOG_DESC       | VARCHAR       | Detailed description           |
| LOG_DATE_TIME  | TIMESTAMP     | Activity timestamp             |

### Database Relationships

```
AUTHENTICATION (1) ─────── (∞) patient_data
     │                            │
     │                            │
     │                            ├─── (1) register
     │                            │
     └─────────────────────────── └─── (∞) INVOICE_LOGS
```

### Key Database Features
- **Referential Integrity**: Foreign key relationships maintain data consistency
- **Transaction History**: Complete audit trail via INVOICE_LOGS
- **Flexible Payment Tracking**: Supports partial payments and multiple payment methods
- **Schema Isolation**: Uses dedicated schema (NEJET) for organization

---

## ⚙️ System Features

### 1. Management Portal Features

#### A. Dashboard (`/`)
- **Overview Statistics**:
  - Total Records
  - Total Revenue
  - Pending Amount
  - Paid Customers Count
- **Recent Activity Log**: Last 10 system activities
- **Quick Access**: Navigation to all management functions

#### B. Create New Record (`/new_record/`)
- Patient selection from dropdown (existing patients)
- Automatic invoice number generation
- Date selection
- Amount entry
- Automatic registration in database

#### C. Update Payment (`/update_record/`)
- Search patient by UID
- View invoice details
- Update payment amount
- Support for multiple payment modes:
  - Cash
  - Card/Online
  - Razorpay integration
- Payment transaction logging

#### D. View All Records (`/view_all/`)
- **Comprehensive Table View**:
  - Patient details
  - Invoice information
  - Payment status
  - Remaining balance
- **Detailed Logs**: Click to view payment history
- **Print Invoice**: Direct link to invoice printout

#### E. Analytics Dashboard (`/analytics/`)
- **Financial Summary**:
  - Total Revenue
  - Total Collected
  - Outstanding Balance
- **Patient Statistics**:
  - Total Patients
  - Average Spending
  - Repeat Patients
  - Top Paying Patients
- **Activity Trends**:
  - Invoice Volume (monthly)
  - Revenue Trends
  - Recent Activity Logs
- **Payment Mode Distribution**:
  - Pie chart visualization
  - Count and amount by payment method
- **AI-Powered Insights**:
  - GROQ AI analysis of financial data
  - Actionable recommendations
  - Trend identification
- **Report Generation**:
  - Custom PDF reports
  - Selectable sections
  - Portrait/Landscape orientation
  - Charts and graphs included

#### F. User Registration (`/register/`)
- New patient registration
- Automatic UID generation
- Unique password creation
- Email validation
- PDF credentials download
- Activity logging

#### G. Authentication
- Secure login for staff
- Session management with cookies
- Password-based authentication
- Auto-logout after 3 hours

### 2. Patient Portal Features

#### A. Patient Dashboard (`/user/<email>/`)
- **Summary Statistics**:
  - Total Invoices
  - Total Amount
  - Pending Dues
  - Unpaid/Paid/Pending Count
- **Payment Summary**:
  - Current month payments
  - Last month payments
- **Recent Transactions**: Last 5 payment activities

#### B. Invoice View (`/user/<email>/invoices/`)
- List of all patient invoices
- Payment status for each invoice
- Remaining balance display
- Payment history access

#### C. Password Reset (`/reset-password/`)
- **OTP-Based Reset**:
  1. Email verification
  2. OTP sent via Resend API
  3. OTP validation (6 digits, 10-minute expiry)
  4. Password update
- **Security Features**:
  - In-memory OTP storage
  - Time-limited codes
  - One-time use verification

### 3. Payment Processing

#### A. Razorpay Integration
- **Payment Window** (`/razorpay_payment/`)
  - Order creation
  - Razorpay checkout UI
  - Payment verification
- **API Endpoints**:
  - `/api/initiate_payment/`: Create Razorpay order
  - `/api/verify_payment/`: Verify payment signature
- **Features**:
  - Secure payment processing
  - Automatic invoice update
  - Transaction logging

#### B. Multiple Payment Methods
- **CASH**: Direct cash payments
- **CARD**: Card payments
- **RAZ** (Razorpay): Online payments
- Each method tracked separately in logs

### 4. Reporting & Analytics

#### A. PDF Report Generation
- **Customizable Sections**:
  - KPI Summary
  - Revenue Trends
  - Payment Modes Distribution
  - Top Patients List
  - Invoice Volume
  - Activity Logs
  - Complete Patient List
- **Chart Types**:
  - Bar charts for trends
  - Pie charts for distributions
  - Tables for detailed data
- **Export Options**:
  - Portrait/Landscape orientation
  - Professional formatting
  - Color-coded visualizations

#### B. AI Insights
- **GROQ AI Integration**:
  - Analyzes financial data
  - Identifies trends and anomalies
  - Provides actionable recommendations
- **Data Analyzed**:
  - Revenue patterns
  - Payment behaviors
  - Outstanding balances
  - Patient statistics
- **Output**:
  - Concise text summary
  - Key highlights
  - Confidence score
  - Data references

---

## 💻 Technology Stack

### Backend Technologies

#### 1. Django Framework (v5.2.7)
- **Web Framework**: Python-based MVC architecture
- **Template Engine**: Django Template Language
- **Session Management**: Cookie-based authentication
- **CSRF Protection**: Built-in security
- **URL Routing**: Clean URL patterns

#### 2. IBM DB2
- **Database System**: Enterprise-grade RDBMS
- **Python Driver**: ibm_db library
- **Connection**: TCP/IP protocol
- **Features Used**:
  - Complex SQL queries
  - Transactions
  - Aggregate functions
  - Subqueries and CTEs
  - Parallel query execution

#### 3. Python Libraries
```python
# Core Dependencies
django==5.2.7
ibm_db==3.x
python-dotenv==1.x

# Payment Processing
razorpay==1.x

# Email Services
resend==0.x

# PDF Generation
reportlab==4.x

# HTTP Requests
requests==2.x

# Web Server
flask==3.x  # For DB2QueryServer
```

### Frontend Technologies

#### 1. HTML5
- Semantic markup
- Responsive templates
- Form validation

#### 2. Tailwind CSS (v3.4.18)
- Utility-first CSS framework
- Responsive design
- Custom color schemes
- Dark mode support

#### 3. JavaScript
- Fetch API for AJAX calls
- Dynamic content updates
- Form handling
- Client-side validation

### External Services

#### 1. Razorpay
- **Purpose**: Payment gateway
- **Features**:
  - Order creation
  - Payment processing
  - Signature verification
- **Mode**: Test mode (configurable)

#### 2. Resend
- **Purpose**: Email delivery
- **Features**:
  - OTP emails
  - HTML email templates
  - Reliable delivery
- **Configuration**: API key-based

#### 3. GROQ AI
- **Purpose**: AI-powered analytics
- **Model**: llama-3.1-8b-instant
- **Features**:
  - Natural language insights
  - Financial analysis
  - Trend detection

### Development Tools

#### 1. Environment Management
```bash
# .env file
SECRET_KEY=<django-secret-key>
DEBUG=True
RAZORPAY_KEY_ID=<razorpay-key>
RAZORPAY_KEY_SECRET=<razorpay-secret>
RESEND_API_KEY=<resend-api-key>
GROQ_API_KEY=<groq-api-key>
GROQ_MODEL=llama-3.1-8b-instant
```

#### 2. Build Tools
- **NPM**: Package management
- **Tailwind CLI**: CSS compilation
- **Django Management**: Server, migrations

---

## 🔧 Implementation Details

### 1. Database Connection Architecture

#### DB2Query Module
Located at: `HealthLedger/DB2/DB2Query.py`

```python
# Connection Configuration
dsn = (
    f"DATABASE={dsn_database};"      # HOSPITAL
    f"HOSTNAME={dsn_hostname};"      # localhost
    f"PORT={dsn_port};"              # 25000
    f"PROTOCOL={dsn_protocol};"      # TCPIP
    f"UID={dsn_uid};"                # db2admin
    f"PWD={dsn_pwd};"                # credentials
)

# Key Functions:
# 1. runQuery(query) - Execute INSERT/UPDATE/DELETE
# 2. runSelectQuery(query) - Execute SELECT, returns list of dicts
# 3. runParallelQueries(queries, max_workers) - Execute multiple queries concurrently
```

**Features**:
- **Auto-commit Mode**: Immediate transaction commit
- **Schema Setting**: Automatic schema selection (NEJET)
- **Error Handling**: Try-catch with detailed error messages
- **Connection Pooling**: Opens/closes connections per query
- **Parallel Execution**: Uses multiprocessing.Pool for concurrent queries

#### Standalone DB2 Query Server
File: `DB2QueryServer.py`

A Flask-based REST API server providing HTTP access to DB2:

**Endpoints**:
```
GET  /get/run/<query>           - Execute DML queries
GET  /get/select/<query>        - Execute SELECT queries
GET  /get/describe/<table>      - Get table schema
POST /post/                     - Execute queries via JSON
GET  /                          - API documentation page
```

**Usage Example**:
```javascript
fetch('http://localhost:9999/post/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        type: 'select',
        query: 'SELECT * FROM patient_data'
    })
})
```

### 2. Authentication System

#### Session Management
```python
# On successful login:
auth_token = hashlib.sha256(email.encode()).hexdigest()
request.session[f'{auth_token}_is_authenticated'] = True
request.session[f'{auth_token}_user_uid'] = user.get('UID')
request.session[f'{auth_token}_user_name'] = user.get('NAME')
request.session[f'{auth_token}_user_email'] = user.get('EMAIL')

# Cookie setting (3-hour expiry)
response.set_cookie('auth_token', auth_token, max_age=10800)
```

#### User Types
- **'S' (Staff)**: Access to management portal
- **'P' (Patient)**: Access to patient portal

#### Password Reset Flow
```
User enters email → OTP generated (6 digits) → 
Email sent via Resend → User enters OTP → 
OTP verified (10-min expiry) → New password set → 
Database updated → OTP cleared
```

### 3. Payment Processing Flow

#### Razorpay Integration
```python
# 1. Create Order
client = razorpay.Client(auth=(KEY_ID, KEY_SECRET))
order = client.order.create({
    'amount': amount_in_paise,  # Amount in smallest currency unit
    'currency': 'INR',
    'payment_capture': 1
})

# 2. User completes payment on Razorpay UI

# 3. Verify Payment Signature
client.utility.verify_payment_signature({
    'razorpay_order_id': order_id,
    'razorpay_payment_id': payment_id,
    'razorpay_signature': signature
})

# 4. Update Database
UPDATE register SET PAID_AMT = <amount>
INSERT INTO INVOICE_LOGS (payment details...)
INSERT INTO activity (log entry...)
```

### 4. Analytics & Reporting

#### AI Insights Generation
```python
# 1. Collect Data
queries = [
    total_revenue_query,
    total_collected_query,
    outstanding_query,
    monthly_trends_query,
    payment_modes_query,
    top_patients_query
]

# 2. Execute in Parallel
success, results = DB2Query.runParallelQueries(queries, max_workers=9)

# 3. Build Context
context = {
    'financial_summary': {...},
    'monthly_trends': [...],
    'payment_modes': [...],
    'top_patients': [...]
}

# 4. Call GROQ AI
response = requests.post('https://api.groq.com/openai/v1/chat/completions', {
    'model': 'llama-3.1-8b-instant',
    'messages': [{'role': 'user', 'content': prompt}],
    'temperature': 0.3
})

# 5. Return Insights
{
    'insights_text': "...",
    'highlights': ["...", "..."],
    'confidence_score': 0.85
}
```

#### PDF Report Generation
Uses ReportLab library:
```python
# Components:
- SimpleDocTemplate: Page layout
- Table: Data grids with styling
- Paragraph: Text with formatting
- Spacer: Vertical spacing
- VerticalBarChart: Bar charts for trends
- Pie: Pie charts for distributions

# Styling:
- TableStyle: Colors, borders, padding
- ParagraphStyle: Fonts, colors, alignment
```

### 5. Data Generation Utility

File: `GenerateData.py`

Generates sample data for testing:
- 500 patient records
- Random Indian names
- Random invoice numbers
- Random dates (2020-2025)
- Random amounts (₹100 - ₹10,000)
- Automatic user account creation
- Email generation from names

### 6. Frontend Architecture

#### Template Structure
```
templates/src/
├── management/       # Staff portal pages
│   ├── DASH.html    # Dashboard with stats
│   ├── CREATE.html  # New invoice form
│   ├── UPDATE.html  # Payment update form
│   ├── VIEW_ALL.html # Invoice table
│   ├── PRINT_INVOICE.html # Invoice print view
│   ├── ANALYTICS.html # Analytics dashboard
│   ├── LOGIN.html   # Login page
│   ├── REGISTER.html # User registration
│   └── RAZORPAY_PAYMENT.html # Payment UI
└── user/            # Patient portal pages
    ├── DASH.html    # Patient dashboard
    ├── INVOICES.html # Invoice list
    └── RESET.html   # Password reset
```

#### Tailwind CSS Integration
```javascript
// tailwind.config.js
export default {
   content: ["./src/**/*.{html,js}"],
   theme: {
     extend: {},
   },
   plugins: [],
}

// Build command:
npx tailwindcss -i ./src/css/input.css -o ./src/css/output.css --watch
```

---

## 📡 API Documentation

### Management APIs

#### 1. Dashboard & Statistics

**Get Overall Statistics**
```http
GET /api/get_stats/

Response:
{
    "total_records": 500,
    "total_revenue": 2500000.00,
    "total_pending_amount": 350000.00,
    "total_paid_customers": 425
}
```

**Recent Activity**
```http
GET /api/recent-activity/

Response:
{
    "activities": [
        {
            "log_name": "Payment Update",
            "log_desc": "Payment done for INV00000123...",
            "log_date_time": "2025-11-05 14:30:00"
        }
    ]
}
```

#### 2. Invoice Management

**Load Paginated Records**
```http
GET /api/load_data/?size=50&offset=0&search=ABC001&date_from=2025-01-01&date_to=2025-12-31&status=pending

Headers:
X-Total-Count: 150

Response:
[
    {
        "recNumber": 1,
        "uid": "ABC001",
        "username": "John Doe",
        "invoiceNum": "INV00000001",
        "date": "2025-01-15",
        "amount": 5000.00,
        "paidAmount": 2000.00,
        "remainingAmount": 3000.00,
        "remark": "Pending",
        "detailed_logs": [...]
    }
]
```

**Get Invoice Details**
```http
GET /api/invoice/INV00000001/

Response:
{
    "recNumber": 1,
    "uid": "ABC001",
    "username": "John Doe",
    "invoiceNum": "INV00000001",
    "date": "2025-01-15",
    "amount": 5000.00,
    "paidAmount": 2000.00,
    "remainingAmount": 3000.00,
    "remark": "Pending",
    "detailed_logs": [
        {
            "date": "2025-01-20",
            "paid_amount_on_date": 2000.00,
            "log_remark": "Payment via CASH"
        }
    ]
}
```

**Add New Invoice**
```http
GET /api/add_new_data/?uid=ABC001&username=John+Doe&invoiceNum=INV00000002&date=2025-11-05&amount=7500

Response:
{
    "status": true,
    "message": "Record added successfully"
}
```

**Update Payment**
```http
GET /api/update_payment/?uid=ABC001&invoice_num=INV00000001&paid_amount=1500&total_amount=5000&by=mode:CASH|id:null

Response:
{
    "message": "Payment updated successfully"
}
```

#### 3. User Management

**Get All Patient UIDs**
```http
GET /api/get_all_uids/

Response:
[
    {
        "uid": "ABC001",
        "name": "John Doe",
        "email": "john.doe@gmail.com"
    }
]
```

**Generate New UID**
```http
GET /api/generate_uid/

Response:
{
    "uid": "ABC502"
}
```

**Generate Invoice Number**
```http
GET /api/generate_invoice_number/

Response:
{
    "invoice_number": "INV00000502"
}
```

**Register New User**
```http
POST /api/register_user/
Content-Type: application/json

{
    "name": "Jane Smith",
    "email": "jane.smith@email.com"
}

Response:
{
    "success": true,
    "uid": "ABC503",
    "password": "1234",
    "pdf_url": "/api/registration_pdf/ABC503/"
}
```

**Get User by UID**
```http
GET /api/get_user_by_uid/?uid=ABC001

Response:
{
    "uid": "ABC001",
    "name": "John Doe",
    "email": "john.doe@gmail.com"
}
```

#### 4. Analytics APIs

**Financial Summary**
```http
GET /api/financial_summary/

Response:
{
    "total_revenue": 2500000.00,
    "total_collected": 2150000.00,
    "outstanding": 350000.00,
    "monthly": [
        {"month": "2025-01", "revenue": 180000.00},
        {"month": "2025-02", "revenue": 195000.00}
    ]
}
```

**Patient Statistics**
```http
GET /api/patient_stats/

Response:
{
    "total_patients": 450,
    "avg_spending": 5555.56,
    "repeat_patients": 120,
    "top_patients": [
        {
            "uid": "ABC045",
            "name": "High Payer",
            "total_paid": 85000.00
        }
    ]
}
```

**Activity Trends**
```http
GET /api/activity_trends/

Response:
{
    "invoice_volume": [
        {"month": "2025-01", "count": 45},
        {"month": "2025-02", "count": 52}
    ],
    "recent_logs": [...]
}
```

**Payment Modes Distribution**
```http
GET /api/payment_modes/

Response:
{
    "modes": ["CASH", "RAZ", "CARD"],
    "counts": [320, 150, 80],
    "amounts": [1200000.00, 750000.00, 200000.00]
}
```

**AI Insights**
```http
POST /api/ai_insights/

Response:
{
    "insights_text": "The financial health shows...",
    "highlights": [
        "Revenue increased by 12% this month",
        "Outstanding balance requires attention"
    ],
    "confidence_score": 0.85,
    "references": {
        "total_invoices": 500,
        "monthly_trend_months": 12,
        "payment_modes_analyzed": 3
    }
}
```

**Generate Report**
```http
POST /api/generate_report/
Content-Type: application/json

{
    "sections": [
        "kpi-section",
        "revenue-trend-section",
        "payment-modes-section",
        "top-patients-section"
    ],
    "orientation": "landscape"
}

Response: PDF file download
```

### Patient APIs

**User Invoices**
```http
GET /api/user/invoices/<base64_email>/

Response:
[
    {
        "recNumber": 1,
        "uid": "ABC001",
        "username": "John Doe",
        "invoiceNum": "INV00000001",
        "date": "2025-01-15",
        "amount": 5000.00,
        "paidAmount": 2000.00,
        "remainingAmount": 3000.00,
        "remark": "Pending"
    }
]
```

**User Statistics**
```http
GET /api/user/stats/<email>/

Response:
{
    "summary": {
        "total_invoices": 5,
        "total_amount": 25000.00,
        "pending_dues": 8000.00,
        "unpaid_count": 1,
        "paid_amount": 17000.00,
        "paid_count": 3,
        "pending_count": 1
    },
    "payment_summary": {
        "this_month": 3000.00,
        "last_month": 5000.00
    },
    "recent_transactions": [...]
}
```

### Payment APIs

**Initiate Razorpay Payment**
```http
POST /api/initiate_payment/
Content-Type: application/json

{
    "amount": 5000,
    "invoice_num": "INV00000001",
    "uid": "ABC001"
}

Response:
{
    "success": true,
    "order_id": "order_xyz123",
    "amount": 500000,
    "currency": "INR",
    "key": "rzp_test_xyz"
}
```

**Verify Payment**
```http
POST /api/verify_payment/

Form Data:
razorpay_payment_id: pay_xyz123
razorpay_order_id: order_xyz123
razorpay_signature: signature_hash
invoice_num: INV00000001
uid: ABC001
amount: 5000
total_amount: 5000

Response:
{
    "success": true,
    "message": "Payment verified and updated successfully",
    "payment_id": "pay_xyz123",
    "invoice_num": "INV00000001",
    "amount_paid": 5000.00
}
```

### Password Reset APIs

**Send OTP**
```http
POST /api/reset-password/send-otp/
Content-Type: application/json

{
    "email": "john.doe@gmail.com"
}

Response:
{
    "success": true,
    "message": "OTP sent successfully"
}
```

**Verify OTP**
```http
POST /api/reset-password/verify-otp/
Content-Type: application/json

{
    "email": "john.doe@gmail.com",
    "otp": "123456"
}

Response:
{
    "success": true,
    "message": "OTP verified successfully"
}
```

**Reset Password**
```http
POST /api/reset-password/reset/
Content-Type: application/json

{
    "email": "john.doe@gmail.com",
    "new_password": "newpass123"
}

Response:
{
    "success": true,
    "message": "Password reset successfully"
}
```

---

## 🔒 Security Features

### 1. Authentication & Authorization

#### Session Security
- **SHA-256 Hashing**: Email-based token generation
- **HTTP-Only Cookies**: Not accessible via JavaScript
- **SameSite Policy**: CSRF protection
- **3-Hour Expiry**: Automatic session timeout
- **Secure Flag**: HTTPS-only in production

#### Access Control
```python
# Route Protection
def DASH(request):
    auth_token = request.COOKIES.get('auth_token')
    if auth_token and request.session.get(f'{auth_token}_is_authenticated'):
        return render(request, 'src/management/DASH.html')
    else:
        return redirect('/login')
```

### 2. SQL Injection Prevention

#### Parameterized Queries
While the current implementation uses string interpolation, best practice would be:
```python
# Current (vulnerable):
query = f"SELECT * FROM patient_data WHERE UID = '{uid}'"

# Recommended:
# Use DB2 parameter markers
query = "SELECT * FROM patient_data WHERE UID = ?"
# Execute with parameters
```

#### Input Sanitization
```python
# Email sanitization
email_s = email.replace("'", "''")  # SQL escape

# Name sanitization
name_s = name.replace("'", "''")
```

### 3. Password Security

#### OTP System
- **6-Digit Codes**: Numeric OTPs
- **10-Minute Expiry**: Time-limited validity
- **One-Time Use**: Deleted after verification
- **In-Memory Storage**: Not persisted to database

#### Password Generation
- **4-Digit Codes**: Initial passwords
- **Uniqueness Check**: No duplicate passwords
- **Random Generation**: Secure random module

### 4. CSRF Protection

Django's built-in CSRF middleware:
```python
# Enabled in settings
MIDDLEWARE = [
    'django.middleware.csrf.CsrfViewMiddleware',
]

# Exempted for specific APIs
@csrf_exempt
def api_verify_payment(request):
    # Payment callback from Razorpay
```

### 5. Environment Variables

Sensitive data in `.env`:
```bash
SECRET_KEY=<unique-django-secret>
RAZORPAY_KEY_ID=<razorpay-public-key>
RAZORPAY_KEY_SECRET=<razorpay-secret-key>
RESEND_API_KEY=<resend-api-key>
GROQ_API_KEY=<groq-api-key>
```

Loaded via python-dotenv:
```python
from dotenv import load_dotenv
load_dotenv()

RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID', 'default_value')
```

### 6. Payment Security

#### Razorpay Signature Verification
```python
# Verify payment authenticity
params_dict = {
    'razorpay_order_id': order_id,
    'razorpay_payment_id': payment_id,
    'razorpay_signature': signature
}

try:
    client.utility.verify_payment_signature(params_dict)
    # Payment is authentic
except razorpay.errors.SignatureVerificationError:
    # Payment is fraudulent
    return JsonResponse({"error": "Invalid signature"}, status=400)
```

### 7. Data Validation

#### Server-Side Validation
```python
# Required field checks
if not uid or not invoice_num or not paid_amount:
    return JsonResponse({"error": "All fields required"}, status=400)

# Type validation
try:
    paid_amount = float(paid_amount)
except ValueError:
    return JsonResponse({"error": "Amount must be numeric"}, status=400)

# Email validation
if not email or '@' not in email:
    return JsonResponse({"error": "Invalid email"}, status=400)
```

### 8. Error Handling

#### Graceful Degradation
```python
try:
    # Database operation
    success, result = DB2Query.runSelectQuery(query)
    if not success:
        return JsonResponse({"error": "Database error"}, status=500)
except Exception as e:
    return JsonResponse({"error": str(e)}, status=500)
```

---

## 🚀 Deployment Guide

### Prerequisites

1. **Python 3.8+**
2. **IBM DB2 Server**
3. **Node.js & NPM** (for Tailwind CSS)
4. **Git** (optional)

### Step 1: Environment Setup

```bash
# Clone repository
git clone https://github.com/tusharneje-07/HealthLedgerDB2.git
cd HealthLedgerDB2/HealthLedger

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install Python dependencies
pip install django==5.2.7
pip install ibm_db
pip install python-dotenv
pip install razorpay
pip install resend
pip install reportlab
pip install requests
pip install flask
```

### Step 2: Database Configuration

```bash
# Install IBM DB2 (if not already installed)
# Download from IBM website
# https://www.ibm.com/products/db2-database

# Create database
db2 CREATE DATABASE HOSPITAL

# Connect to database
db2 CONNECT TO HOSPITAL

# Create schema
db2 CREATE SCHEMA NEJET

# Set current schema
db2 SET CURRENT SCHEMA = NEJET

# Create tables (run SQL scripts)
db2 -tvf create_tables.sql
```

**Table Creation SQL**:
```sql
-- AUTHENTICATION table
CREATE TABLE AUTHENTICATION (
    UID VARCHAR(50) NOT NULL PRIMARY KEY,
    NAME VARCHAR(200),
    EMAIL VARCHAR(200) UNIQUE,
    PASSWORD VARCHAR(100),
    FLAG CHAR(1),
    KEY VARCHAR(500)
);

-- patient_data table
CREATE TABLE patient_data (
    REC_NUMBER INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    UID VARCHAR(50),
    USERNAME VARCHAR(200),
    INNVOCE_NUM VARCHAR(50) UNIQUE,
    DATE DATE,
    AMOUNT DECIMAL(15,2)
);

-- register table
CREATE TABLE register (
    UID VARCHAR(50),
    INNVOCE_NUM VARCHAR(50),
    PAID_AMT DECIMAL(15,2)
);

-- INVOICE_LOGS table
CREATE TABLE INVOICE_LOGS (
    INVOICE_NUMBER VARCHAR(50),
    UID VARCHAR(50),
    LOG_DATE TIMESTAMP,
    AMOUNT DECIMAL(15,2),
    PAID_AMOUNT_ON_DATE DECIMAL(15,2),
    REMAINING_AMOUNT_ON_DATE DECIMAL(15,2),
    LOG_REMARK VARCHAR(500),
    PAYMENT_MODE VARCHAR(20),
    PAYMENT_ID VARCHAR(200)
);

-- activity table
CREATE TABLE activity (
    LOG_NAME VARCHAR(200),
    LOG_DESC VARCHAR(500),
    LOG_DATE_TIME TIMESTAMP
);
```

### Step 3: Environment Variables

Create `.env` file in HealthLedger directory:
```bash
# Django
SECRET_KEY=your-secret-key-here
DEBUG=True

# Razorpay
RAZORPAY_KEY_ID=rzp_test_your_key
RAZORPAY_KEY_SECRET=your_secret_key

# Resend (Email)
RESEND_API_KEY=re_your_api_key

# GROQ AI
GROQ_API_KEY=gsk_your_api_key
GROQ_MODEL=llama-3.1-8b-instant
```

### Step 4: Frontend Build

```bash
cd templates

# Install NPM dependencies
npm install

# Build Tailwind CSS
npx tailwindcss -i ./src/css/input.css -o ./src/css/output.css --minify

# For development (watch mode)
npx tailwindcss -i ./src/css/input.css -o ./src/css/output.css --watch
```

### Step 5: Django Configuration

Update `HealthLedger/settings.py`:
```python
# DB2 connection in DB2Query.py
dsn_hostname = "localhost"  # or your DB2 server IP
dsn_uid = "db2admin"        # your DB2 username
dsn_pwd = "your_password"   # your DB2 password
dsn_database = "HOSPITAL"
dsn_port = "25000"          # default DB2 port is 50000
dsn_protocol = "TCPIP"

# Allowed hosts for production
ALLOWED_HOSTS = ["*"]  # Change to your domain in production

# CSRF trusted origins
CSRF_TRUSTED_ORIGINS = ["https://your-domain.com"]
```

### Step 6: Generate Sample Data (Optional)

```bash
# Edit GenerateData.py with correct DB2 credentials
python HealthLedger/GenerateData.py
```

### Step 7: Run Development Server

```bash
# Navigate to HealthLedger directory
cd HealthLedger

# Run Django server
python manage.py runserver 0.0.0.0:8000

# In separate terminal, run DB2 Query Server (optional)
python DB2QueryServer.py
```

### Step 8: Access Application

- **Management Portal**: http://localhost:8000/
- **Patient Login**: http://localhost:8000/login/patient/
- **DB2 API Server**: http://localhost:9999/

### Production Deployment

#### 1. Use Production WSGI Server
```bash
# Install Gunicorn
pip install gunicorn

# Run with Gunicorn
gunicorn HealthLedger.wsgi:application --bind 0.0.0.0:8000 --workers 4
```

#### 2. Setup Nginx Reverse Proxy
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /static/ {
        alias /path/to/HealthLedger/templates/src/;
    }
}
```

#### 3. Setup SSL Certificate
```bash
# Using Let's Encrypt
sudo certbot --nginx -d your-domain.com
```

#### 4. Environment Configuration
```python
# settings.py for production
DEBUG = False
ALLOWED_HOSTS = ['your-domain.com']
CSRF_TRUSTED_ORIGINS = ['https://your-domain.com']

# Use environment variables
SECRET_KEY = os.getenv('SECRET_KEY')
```

#### 5. Database Optimization
```sql
-- Create indexes for better performance
CREATE INDEX idx_patient_uid ON patient_data(UID);
CREATE INDEX idx_patient_invoice ON patient_data(INNVOCE_NUM);
CREATE INDEX idx_invoice_logs ON INVOICE_LOGS(INVOICE_NUMBER);
CREATE INDEX idx_auth_email ON AUTHENTICATION(EMAIL);
```

---

## 👥 User Workflows

### Management Staff Workflow

#### 1. Login
```
1. Navigate to http://localhost:8000/login
2. Enter credentials (UID or Email + Password)
3. Select user type: Staff
4. Click Login
5. Redirected to Dashboard
```

#### 2. Create New Invoice
```
1. From Dashboard, click "New Record"
2. Select patient from dropdown
3. Invoice number auto-generated
4. Enter date
5. Enter amount
6. Click Submit
7. System creates:
   - patient_data record
   - register record (paid_amt = 0)
   - activity log
```

#### 3. Update Payment
```
1. From Dashboard, click "Update Payment"
2. Enter patient UID
3. System displays invoice details
4. Enter payment amount
5. Select payment mode:
   - Cash: Enter amount directly
   - Online: Redirected to Razorpay
6. Click Update
7. System updates:
   - register.PAID_AMT
   - Creates INVOICE_LOGS entry
   - Creates activity log
```

#### 4. View All Records
```
1. From Dashboard, click "View All"
2. Table displays:
   - All invoices
   - Patient names
   - Payment status
   - Remaining balance
3. Click on invoice for details
4. View payment history
5. Print invoice if needed
```

#### 5. Analytics Dashboard
```
1. From Dashboard, click "Analytics"
2. View sections:
   - Financial Summary (KPIs)
   - Patient Statistics
   - Revenue Trends (charts)
   - Payment Mode Distribution
   - AI Insights
3. Generate custom reports:
   - Select sections
   - Choose orientation
   - Download PDF
```

#### 6. Register New Patient
```
1. From Dashboard, click "Register"
2. Enter patient name
3. Enter email address
4. Click Register
5. System:
   - Generates unique UID
   - Creates random password
   - Sends credentials email
   - Provides PDF download
```

### Patient Workflow

#### 1. Login
```
1. Navigate to http://localhost:8000/login/patient/
2. Enter email and password
3. Click Login
4. Redirected to Patient Dashboard
```

#### 2. View Dashboard
```
1. Dashboard displays:
   - Total invoices
   - Total amount owed
   - Pending dues
   - Payment summary (this month vs last month)
   - Recent transactions
```

#### 3. View Invoices
```
1. Click "My Invoices"
2. Table shows:
   - All patient invoices
   - Amounts
   - Payment status
   - Remaining balance
3. Click invoice for details
```

#### 4. Make Payment
```
1. From invoice view, click "Pay Now"
2. Enter amount to pay
3. Redirected to Razorpay
4. Complete payment
5. Redirected back with confirmation
6. Invoice updated automatically
```

#### 5. Reset Password
```
1. Click "Forgot Password" on login
2. Enter email address
3. Receive OTP via email (6 digits, 10-min expiry)
4. Enter OTP
5. Enter new password
6. Click Reset
7. Password updated
8. Login with new password
```

---

## 🔮 Future Enhancements

### Planned Features

#### 1. Advanced Analytics
- **Predictive Analytics**: ML models for revenue forecasting
- **Patient Segmentation**: Classify patients by payment behavior
- **Anomaly Detection**: Identify unusual transactions
- **Custom Dashboards**: User-configurable analytics views

#### 2. Enhanced Patient Portal
- **Appointment Scheduling**: Integrate appointment management
- **Medical Records**: View test results and prescriptions
- **Chat Support**: Real-time support chat
- **Mobile App**: Native iOS/Android applications

#### 3. Payment Enhancements
- **Recurring Payments**: Subscription-based billing
- **Payment Plans**: Installment options
- **Multiple Gateways**: Support for Stripe, PayPal
- **Wallet System**: In-app wallet for faster payments

#### 4. Reporting Improvements
- **Excel Export**: Export data to Excel/CSV
- **Scheduled Reports**: Automatic email reports
- **Custom Templates**: User-designed report templates
- **Interactive Dashboards**: Real-time data visualization

#### 5. Security Enhancements
- **Two-Factor Authentication**: SMS/Email 2FA
- **Biometric Login**: Fingerprint/Face ID
- **Audit Logging**: Comprehensive activity tracking
- **Role-Based Access**: Granular permissions

#### 6. Integration Capabilities
- **EHR Integration**: Connect with Electronic Health Records
- **Insurance APIs**: Direct insurance claim processing
- **Accounting Software**: QuickBooks, Tally integration
- **SMS Notifications**: Payment reminders via SMS

#### 7. Performance Optimization
- **Caching Layer**: Redis for session and query caching
- **Database Optimization**: Query optimization, indexing
- **CDN Integration**: Static file delivery via CDN
- **Load Balancing**: Horizontal scaling support

#### 8. User Experience
- **Multi-language Support**: Internationalization (i18n)
- **Dark Mode**: System-wide dark theme
- **Accessibility**: WCAG compliance
- **Progressive Web App**: Offline capability

#### 9. Administrative Tools
- **Bulk Operations**: Mass invoice generation
- **Data Import/Export**: CSV/Excel import
- **System Monitoring**: Health checks and alerts
- **Backup & Restore**: Automated backups

#### 10. Compliance & Legal
- **HIPAA Compliance**: Healthcare data privacy
- **GDPR Compliance**: Data protection regulations
- **Digital Signatures**: Legal document signing
- **Encryption**: End-to-end data encryption

---

## 📚 Conclusion

HealthLedger represents a comprehensive solution for hospital billing and patient management, combining:

### Technical Strengths
- **Enterprise Database**: IBM DB2 for reliability and performance
- **Modern Framework**: Django for rapid development
- **Scalable Architecture**: Modular design for easy expansion
- **Third-party Integrations**: Payment, email, and AI services

### Business Value
- **Efficiency**: Streamlined invoice and payment management
- **Accessibility**: Patient self-service portal reduces support burden
- **Insights**: AI-powered analytics for informed decision-making
- **Transparency**: Complete audit trail and payment history

### Development Quality
- **Code Organization**: Well-structured with separation of concerns
- **Documentation**: Comprehensive inline comments and external docs
- **Error Handling**: Robust error management throughout
- **Extensibility**: Easy to add new features and integrations

### Learning Outcomes
This project demonstrates proficiency in:
- Full-stack web development
- Database design and SQL
- API integration and development
- Payment gateway implementation
- Security best practices
- Frontend responsive design
- System architecture planning

---

## 📞 Contact & Support

### Project Information
- **Project Name**: HealthLedger
- **Repository**: [HealthLedgerDB2](https://github.com/tusharneje-07/HealthLedgerDB2)
- **Owner**: Tushar Neje
- **Email**: Contact via GitHub profile

### Documentation
- **DB2 Query Documentation**: See `DB2Q.md` for detailed SQL explanations
- **API Server Documentation**: Access at http://localhost:9999/ when running
- **This Document**: `PRJ_EXP.md` - Comprehensive project explanation

### Getting Help
1. Check the documentation files
2. Review error logs in terminal
3. Verify environment variables in `.env`
4. Ensure DB2 server is running
5. Check database connection settings

---

## 📄 License & Credits

### Technologies Used
- **Django**: BSD License
- **IBM DB2**: Commercial License
- **Razorpay**: Commercial Service
- **Resend**: Commercial Service
- **GROQ AI**: Commercial Service
- **Tailwind CSS**: MIT License
- **ReportLab**: BSD License

### Acknowledgments
- Django Software Foundation
- IBM for DB2 documentation
- Razorpay for payment gateway
- GROQ for AI services
- Open-source community

---

**Document Version**: 1.0  
**Last Updated**: November 5, 2025  
**Author**: Tushar Neje  
**Project**: HealthLedger - Hospital Billing & Patient Management System

---

*This comprehensive documentation covers all technical and non-technical aspects of the HealthLedger project. For specific implementation details, refer to the source code and additional documentation files.*
