# Smart Sales & Inventory AI Tracking System

![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-brightgreen)
![Python](https://img.shields.io/badge/Python-3.14-blue)
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

- **Authentication** — User registration and login secured with JWT
- **Multi-Business Support** — One user can own and manage multiple businesses
- **Product Management** — Full CRUD operations on products per business
- **Sales Tracking** — Record, retrieve, update, and delete sales transactions with automatic calculations
- **Business Approvals** — Request and manage business join approvals with role-based access control
- **Customer Management** — Create, update, and manage customers per business
- **Debt Tracking** — Track outstanding customer debts with auto-reminders
- **Automated Reports** — Daily, weekly, and monthly sales summaries sent via email to admins and managers using background cron jobs

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI |
| Database | PostgreSQL |
| Auth | JWT (OAuth2) |
| Background Jobs | APScheduler / Celery |
| Email | SMTP |
| Deployment | Render / Railway |

---

## Project Structure

```
src/
├── main.py                # App entry point, CORS, router registration
├── config.py              # Pydantic settings (env vars)
├── database.py            # SQLAlchemy engine, session, Base
├── auth/                  # Authentication module
│   ├── router.py          #   /auth/register, /auth/login
│   ├── schemas.py         #   Request/response models
│   ├── service.py         #   Registration & login logic
│   ├── dependencies.py    #   OAuth2 scheme, get_current_user
│   └── utils.py           #   Password hashing, JWT helpers
├── users/                 # User management module
│   ├── router.py          #   /users endpoints
│   ├── models.py          #   Users, BusinessMember, RoleEnum
│   ├── schemas.py         #   Request/response models
│   ├── service.py         #   User CRUD logic
│   └── dependencies.py    #   Role-based access helpers
├── businesses/            # Business, product, sales, approvals module
│   ├── router.py          #   /businesses, /products, /sales, /approvals, /reports, /admin/crons
│   ├── models.py          #   Business, Product, Sale, SalesItem, Debt, Approvals
│   ├── schemas.py         #   Request/response models
│   └── service.py         #   Business logic
├── customers/             # Customer management module
│   ├── router.py          #   /business/customers endpoints
│   ├── models.py          #   Customer model
│   ├── schemas.py         #   Request/response models
│   └── service.py         #   Customer CRUD logic
├── debts/                 # Debt tracking module
│   ├── router.py          #   /debts endpoints
│   ├── models.py          #   Re-exports Debt from businesses
│   ├── schemas.py         #   Request/response models
│   └── service.py         #   Debt management logic
├── celery_tasks/          # Background job module
│   ├── worker.py          #   Celery app
│   ├── tasks.py           #   Daily/weekly/monthly summary tasks
│   ├── scheduler.py       #   APScheduler job definitions
│   └── email_report.py    #   Email report builder
├── middleware/
│   └── logging.py         # Request logging middleware
└── errors/
    └── handlers.py        # Global exception handlers

alembic/                   # Database migrations
tests/                     # Pytest test suite
├── conftest.py            # Shared fixtures
├── auth/
├── users/
├── debts/
├── test_businesses.py
├── test_products.py
├── test_sales.py
├── test_customers.py
├── test_approvals.py
├── test_reports.py
└── test_users.py

railway.yaml               # Railway deployment config
render.yaml                # Render deployment config
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
| `/auth/register` | POST | Create a new user account |
| `/auth/login` | POST | Login and receive JWT token |

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
| `/business/customers/{business_id}/{customer_id}` | DELETE | Soft-delete a customer |

---

## Debts

| Endpoint | Method | Description |
|---|---|---|
| `/debts/` | GET | Get outstanding debts for current business |

---

## Approvals

| Endpoint | Method | Description |
|---|---|---|
| `/approvals/send_approval` | POST | Send a business join request |
| `/approvals/get_approvals/{business_id}` | GET | Get approvals (filterable by status) |
| `/approvals/confirm_approvals/{business_id}` | POST | Approve or reject an approval |

---

## Reports & Analytics

| Endpoint | Method | Description |
|---|---|---|
| `/reports/profit/{business_id}` | GET | View profit, revenue, cost |
| `/reports/analytics/summery/{business_id}` | GET | Full sales summary (emailed) |
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

---

## Environment Variables

Create a `.env` file in the project root:

```env
DATABASE_URL=postgresql://user:password@host/dbname
SECRET_KEY=your_secret_key
SUPER_ADMIN_EMAIL=admin@example.com
SUPER_ADMIN_APP_PASSWORD=your_email_app_password
SUPER_ADMIN_NAME=Admin Name
```

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
Backend Engineer — building for African markets  
[GitHub](https://github.com/AJ-190) · [LinkedIn](https://linkedin.com/in/your-profile)

---

## License

This project is licensed under the MIT License.
