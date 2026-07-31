# Smart Sales & Inventory AI Tracking System

![FastAPI](https://img.shields.io/badge/FastAPI-0.136+-brightgreen)
![Python](https://img.shields.io/badge/Python-3.13+-blue)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Supabase-336791)
![License](https://img.shields.io/badge/license-MIT-blue)
![Deploy](https://img.shields.io/badge/deployed-Render-46E3B7)

A production-ready REST API for small businesses to manage inventory, track sales, handle business approvals, and receive automated performance reports — built with FastAPI and PostgreSQL.

---

## Live API

**Base URL:** `https://smart-sales-inventory.onrender.com`  
**Interactive Docs:** `https://smart-sales-inventory.onrender.com/docs`

---

## Features

- **Authentication** — User registration and login secured with JWT + OTP email verification
- **Multi-Business Support** — One user can own and manage multiple businesses
- **Product Management** — Full CRUD operations on products per business
- **Sales Tracking** — Record, retrieve, update, and delete sales transactions with automatic calculations
- **Business Approvals** — Request and manage business join approvals with role-based access control
- **Customer Management** — Create, update, and manage customers per business
- **Debt Tracking** — Track outstanding customer debts with automatic SMS reminders
- **Scheduled SMS Reminders** — Schedule debt reminders and send them via Africa's Talking (sandbox/live)
- **Dashboard & Analytics** — Aggregated KPIs, revenue breakdowns, profit margins, payment method splits, best-selling product insights, and a combined dashboard endpoint
- **Automated Reports** — Daily, weekly, and monthly sales summaries sent via email to admins and managers using background cron jobs

---

## Tech Stack

| Layer | Technology |
|---|---|---|
| Framework | FastAPI |
| Database | PostgreSQL (SQLAlchemy ORM) |
| Auth | JWT (OAuth2 + Argon2 hashing) |
| Background Jobs | Celery + Celery Beat |
| Email | SendGrid (OTP) + SMTP/Gmail (reports) |
| SMS | Africa's Talking (sandbox / live) |
| Caching | Redis (OTP storage, rate limiting, JWT revocation, Celery broker) |
| Deployment | Render / Railway |

---

## Project Structure

```
src/
├── main.py                # App entry point, CORS, router registration
├── config.py              # Pydantic settings (env vars)
├── database.py            # SQLAlchemy engine, session factory, Base
├── httpx_client.py        # Shared HTTPX async client dependency
├── mail.py                # Email utility (fastapi-mail)
├── redis_cllient.py       # Redis async connection helper *(unused — legacy)*
├── auth/                  # Authentication module
│   ├── router.py          #   /auth/login, /auth/refresh, /auth/logout, /auth/otp/*
│   ├── schemas.py         #   Request/response models
│   ├── service.py         #   Login, refresh, logout logic
│   ├── dependencies.py    #   OAuth2 scheme, get_current_user
│   └── utils.py           #   Password hashing (Argon2), JWT helpers
├── users/                 # User management module
│   ├── router.py          #   /users/sign_up, /users/* CRUD
│   ├── models.py          #   Users, BusinessMember, RoleEnum
│   ├── schemas.py         #   Request/response models
│   ├── service.py         #   User CRUD logic
│   └── dependencies.py    #   User-specific dependencies
├── businesses/            # Business management + approvals
│   ├── router.py          #   /businesses/* CRUD, /businesses/approvals/*
│   ├── models.py          #   Business, Product, Sale, SalesItem, Debt, Approvals
│   ├── schemas.py         #   Request/response models
│   └── service.py         #   All business logic
├── products/              # Product management module
│   ├── router.py          #   /products/{business_id}/* CRUD
│   ├── schemas.py         #   Request/response models
│   └── service.py         #   Product CRUD + restock logic
├── sales/                 # Sales tracking module
│   ├── router.py          #   /sales/{business_id}/* CRUD
│   ├── schemas.py         #   Request/response models
│   └── service.py         #   Sales logic with auto-calculations
├── customers/             # Customer management module
│   ├── router.py          #   /business/customers/* CRUD
│   ├── models.py          #   Customer model
│   ├── schemas.py         #   Request/response models
│   └── service.py         #   Customer CRUD logic
├── debts/                 # Debt tracking + reminders module
│   ├── router.py          #   /debts/{business_id}, /debts/customers/{business_id}, /debts/reminders/{business_id}
│   ├── models.py          #   Debt, Transactions, Reminders
│   ├── schemas.py         #   Request/response models
│   └── service.py         #   Debt query + reminder scheduling logic
├── analytics/             # Dashboard & analytics module
│   ├── router.py          #   /reports/*, /admin/crons/*
│   ├── schemas.py         #   Request/response models
│   └── service.py         #   Analytics aggregation logic
├── celery_tasks/          # Background job module (Celery + Beat)
│   ├── celery_app.py      #   Celery config + beat schedule
│   ├── sales_task.py      #   Daily/weekly/monthly summary generators
│   ├── email_report.py    #   HTML email builder + PDF receipt renderer
│   ├── otp_task.py        #   OTP email verification task
│   └── debt_reminders.py  #   Daily SMS debt-reminder dispatcher
├── middleware/
│   ├── __init__.py
│   ├── logging.py         #   Request logging middleware
│   └── auth_middleware.py #   Auth enforcement middleware
├── errors/
│   ├── __init__.py
│   └── handlers.py        #   Global exception handlers
└── db/
    └── redis.py           #   Redis async client (used by main.py)

alembic/                   # Database migrations
tests/                     # Pytest test suite
├── conftest.py            # Shared fixtures, factories
├── auth/
│   ├── test_auth.py
│   └── test_otp.py
├── users/
│   └── test_users.py
├── debts/
│   └── test_debts.py
├── test_businesses.py
├── test_business_members.py
├── test_products.py
├── test_sales.py
├── test_customers.py
├── test_approvals.py
├── test_reports.py
├── test_users.py
└── test_rate_limiter.py

railway.yaml               # Railway deployment config
render.yaml                # Render deployment config
Dockerfile                 # Docker build config (Python 3.13-slim)
Procfile                   # Heroku/Render process file
requirements.txt
```

---

## Authentication

All protected routes require a Bearer token in the `Authorization` header.

```
Authorization: Bearer <your_token>
```

| Endpoint | Method | Description |
|---|---|---|
| `/users/sign_up` | POST | Create a new user account |
| `/auth/login` | POST | Login and receive JWT + refresh token |
| `/auth/refresh` | POST | Refresh an expired access token |
| `/auth/logout` | POST | Invalidate refresh token |
| `/auth/otp/get_code` | POST | Request OTP verification code via email |
| `/auth/otp/verification` | POST | Verify OTP code |

---

## Users

| Endpoint | Method | Description |
|---|---|---|
| `/users/sign_up` | POST | Register a new user |
| `/users/` | GET | List all users with business names (super admin) |
| `/users/members` | GET | List members of current business |
| `/users/all_users` | GET | List all users (super admin) |
| `/users/{id}` | GET | Get a single user |
| `/users/{id}` | PUT | Update a user |
| `/users/{id}` | DELETE | Delete a user |
| `/users/{id}/activate` | PUT | Toggle user active status |

---

## Businesses

| Endpoint | Method | Description |
|---|---|---|
| `/businesses/create` | POST | Create a new business |
| `/businesses/my_businesses` | GET | Get all businesses for current user |
| `/businesses/` | GET | Get all businesses (super admin) |
| `/businesses/{id}` | GET | Get a single business |
| `/businesses/{id}` | PUT | Update a business |
| `/businesses/{id}` | DELETE | Delete a business |
| `/businesses/business_key/{business_id}` | GET | Get business join key |
| `/businesses/{business_id}/members/{member_id}` | PUT | Update a business member's role or active status |

---

## Business Members

| Endpoint | Method | Description |
|---|---|---|
| `/businesses/{business_id}/members/{member_id}` | PUT | Update member role and/or active status |

**Request body:**
```json
{
  "role": "manager",
  "is_active": false
}
```

Both fields are optional. Valid roles: `super_admin`, `admin`, `user`, `manager`, `cashier`, `viewer`.

Only `super_admin`, `admin`, and `manager` roles can update members. Non-super-admins can only update members within their own business.

---

## Products

| Endpoint | Method | Description |
|---|---|---|
| `/products/{business_id}` | POST | Add a product |
| `/products/{business_id}` | GET | Get all products |
| `/products/{business_id}/{id}` | GET | Get a single product |
| `/products/{business_id}/{id}` | PUT | Update a product |
| `/products/{business_id}/{id}` | DELETE | Delete a product |
| `/products/{business_id}/{id}/restock` | POST | Restock a product |
| `/products/{business_id}/low_stock` | GET | Get low stock products |
| `/products/{business_id}/{id}/deactivate` | PUT | Toggle product active status |

---

## Sales

| Endpoint | Method | Description |
|---|---|---|
| `/sales/{business_id}` | POST | Record a sale (auto-calculates totals) |
| `/sales/{business_id}` | GET | Get all sales for a business |
| `/sales/{business_id}/{id}` | GET | Get a single sale |
| `/sales/{business_id}/{id}` | DELETE | Delete a sale |

---

## Customers

| Endpoint | Method | Description |
|---|---|---|
| `/business/customers/{business_id}` | POST | Create a new customer |
| `/business/customers/{business_id}` | GET | Get all customers |
| `/business/customers/{business_id}/{customer_id}` | GET | Get a single customer |
| `/business/customers/{business_id}/{customer_id}` | PUT | Update a customer |
| `/business/customers/{business_id}/deactivate/{customer_id}` | PUT | Deactivate a customer |
| `/business/customers/{business_id}/{customer_id}` | DELETE | Soft-delete a customer |

---

## Debts

| Endpoint | Method | Description |
|---|---|---|
| `/debts/{business_id}` | GET | Get outstanding debts for a business |
| `/debts/customers/{business_id}` | GET | Get customers with outstanding debt |
| `/debts/customers/{business_id}/{customer_id}` | GET | Get a single customer with their outstanding debt |
| `/debts/update_customer_debt/{business_id}/{customer_id}` | PUT | Record a payment / settle a debt |
| `/debts/customer_transactions/{business_id}/{customer_id}` | GET | Get payment history for a customer |
| `/debts/reminders/{business_id}` | POST | Schedule an SMS reminder for a debt |

---

## Scheduled Debt Reminders

Business admins, managers, and cashiers can schedule an automatic SMS reminder for a customer's outstanding debt. A Celery Beat job runs daily at **09:00 UTC** and sends an SMS for every active reminder whose date window includes today, as long as the debt is still unpaid.

**Schedule a reminder:**

```
POST /debts/reminders/{business_id}
Authorization: Bearer <token>   (roles: admin, manager, cashier, super_admin)
```

```json
{
  "debt_id": 12,
  "customer_id": 7,
  "start_date": "2026-07-28",
  "end_date": "2026-07-31",
  "time_of_day": "09:00",
  "note": "Friendly follow-up on your balance"
}
```

`start_date` and `end_date` default to the debt's due date minus 3 days and the due date respectively. `time_of_day` defaults to `09:00`. The SMS is sent to the customer's phone via the Africa's Talking API.

**Beat schedule** (`src/celery_tasks/celery_app.py`):

| Job | Schedule |
|---|---|
| Daily sales summary | Every day at 00:00 UTC |
| Weekly sales summary | Every Monday at 00:00 UTC |
| Monthly sales summary | 1st of the month at 00:00 UTC |
| Debt reminders | Every day at 09:00 UTC |

Run the worker and beat scheduler locally:

```bash
celery -A src.celery_tasks.celery_app worker --loglevel=info
celery -A src.celery_tasks.celery_app beat --loglevel=info
```

---

## Approvals

| Endpoint | Method | Description |
|---|---|---|
| `/businesses/approvals/send_approval` | POST | Send a business join request |
| `/businesses/approvals/get_approvals/{business_id}` | GET | Get approvals (filterable by status) |
| `/businesses/approvals/confirm_approvals/{business_id}` | POST | Approve or reject an approval |

---

## Dashboard / Analytics

A combined dashboard endpoint can aggregate all KPIs into a single response.  
The following data points are available via existing endpoints:

| Metric | Source |
|---|---|
| Total Revenue | `Sale.total_amount` sum |
| Total Profit | `Sale.profit` sum |
| Profit Margin | (profit / revenue) × 100 |
| Sales Count | `Sale.sale_id` count |
| Units Sold | `SalesItem.quantity` sum |
| Payment Split | Cash / Card / Mobile Money counts |
| Best-Selling Product | Product with highest units sold |
| Low Stock Items | Products below threshold |
| Outstanding Debt | Unpaid `Debt.amount` sum |
| Active Products | Product count |
| Total Customers | Customer count |

**Existing analytics endpoints:**

| Endpoint | Method | Description |
|---|---|---|
| `/reports/profit/{business_id}` | GET | View profit, revenue, cost |
| `/reports/analytics/dashboard/{business_id}` | GET | Full dashboard with all KPIs |
| `/reports/analytics/summery/{business_id}` | GET | Full sales summary (also emailed) |
| `/reports/analytics/low_stock` | GET | Low stock alert list |
| `/reports/analytics/debts/{business_id}` | GET | Outstanding debt totals |

---

## Admin Cron Triggers

| Endpoint | Method | Description |
|---|---|---|
| `/admin/crons/daily_summery` | POST | Trigger daily sales report |
| `/admin/crons/weekly_summery` | POST | Trigger weekly sales report |
| `/admin/crons/monthly_summery` | POST | Trigger monthly sales report |
| `/admin/crons/jobs` | GET | List scheduled cron jobs |

---

## Automated Reports

Background cron jobs run on schedule and email reports to business admins and managers:

- **Daily** — End-of-day sales summary
- **Weekly** — Weekly performance overview
- **Monthly** — Monthly revenue and inventory report
- **Debt Reminders** — Daily SMS reminders for scheduled outstanding debts (see [Scheduled Debt Reminders](#scheduled-debt-reminders))

---

## Environment Variables

Create a `.env` file in the project root:

```env
# Database
DATABASE_URL=postgresql://user:password@host:5432/dbname

# JWT Auth
SECRET_KEY=your_jwt_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_TIME=60
REFRESH_TOKEN_TIME=10080

# Super Admin / Email (SMTP)
SUPER_ADMIN_EMAIL=admin@example.com
SUPER_ADMIN_APP_PASSWORD=your_gmail_app_password
SUPER_ADMIN_NAME=Admin Name
MAIL_SERVER=smtp.gmail.com

# API Key
API_AUTH_KEY=your_api_auth_key

# SendGrid (OTP emails)
SENDGRID_API_KEY=your_sendgrid_api_key

# Africa's Talking (debt reminder SMS)
# Sandbox: username is always "sandbox", URL below is the sandbox endpoint
SMS_KEY=your_africastalking_api_key
SMS_USERNAME=sandbox
SMS_SENDER_ID=your_sender_id_or_blank
SMS_API_URL=https://api.sandbox.africastalking.com/version1/messaging

# Redis *(optional)*
REDIS_URL=redis://localhost:6379
```

> **Note:** `SMS_API_URL` defaults to the Africa's Talking **sandbox** endpoint. Switch to `https://api.africastalking.com/version1/messaging` (and set `SMS_USERNAME` to your live app username) to send real SMS. Sandbox sends are simulated — they appear in the Africa's Talking dashboard but are never delivered to real phones.

---

## Running Locally

```bash
# Clone the repo
git clone https://github.com/AJ-190/Smart-Sales-and-inventory-AI-tracking-system.git
cd Smart-Sales-and-inventory-AI-tracking-system

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start the server
uvicorn src.main:app --reload

# Run with production settings
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

---

## Running Tests

```bash
# Run all tests
pytest -v

# Run with output
pytest -v -s

# Run specific test file
pytest -v tests/test_sales.py
```

---

## Deployment

### Docker

Build and run locally:

```bash
docker build -t smart-sales-inventory .
docker run -p 8000:8000 --env-file .env smart-sales-inventory
```

### Render

Push to your Render-connected Git branch. The `render.yaml` will be auto-detected.

### Railway

Deploy via Git or the Railway CLI. The `railway.yaml` specifies:

```yaml
build:
  builder: NIXPACKS

deploy:
  startCommand: python -m uvicorn src.main:app --host 0.0.0.0 --port $PORT
  restartPolicyType: ON_FAILURE
  restartPolicyMaxRetries: 3
```

---

## Author

**Addy Samuel**  
Backend Engineer — The Unfathomable Builder 🫥  
[GitHub](https://github.com/AJ-190) · [LinkedIn](https://linkedin.com/in/your-profile)

---

## License

This project is licensed under the MIT License.
