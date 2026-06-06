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
- **Automated Reports** — Daily, weekly, and monthly sales summaries sent via email to admins and managers using background cron jobs
- **Customer Debt Tracker and Auto Reminders** - Never lose track of who owes you, we remind them so you don't have to.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI |
| Database | PostgreSQL |
| Auth | JWT (OAuth2) |
| Background Jobs | APScheduler / Cron |
| Email | SMTP |
| Deployment | Render |

---

## Project Structure

```
business-bot-v1/
├── app/
│   ├── main.py          # App entry point, router registration
│   ├── models.py        # Database models
│   ├── schemas.py       # Pydantic schemas
│   ├── database.py      # DB connection
│   ├── routers/         # Route handlers
│   ├── services/        # Business logic
│   ├── jobs/            # Background jobs
│   └── core/
│       └── config.py    # Environment config
├── alembic/             # Database migrations
├── tests/               # Pytest test suite
├── render.yaml          # Render deployment config
├── requirements.txt
└── .env                 # Environment variables (not committed)
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
| `/businesses` | POST | Create a new business |
| `/businesses` | GET | Get all businesses for current user |
| `/businesses/{id}` | GET | Get a single business |
| `/businesses/{id}` | PUT | Update a business |
| `/businesses/{id}` | DELETE | Delete a business |

---

## Products

| Endpoint | Method | Description |
|---|---|---|
| `/products/{business_id}` | POST | Add a product to a business |
| `/products/{business_id}` | GET | Get all products for a business |
| `/products/{business_id}/{product_id}` | GET | Get a single product |
| `/products/{business_id}/{product_id}` | PUT | Update a product |
| `/products/{business_id}/{product_id}` | DELETE | Delete a product |

---

## Sales

| Endpoint | Method | Description |
|---|---|---|
| `/sales/{business_id}` | POST | Record a sale (auto-calculates totals) |
| `/sales/{business_id}` | GET | Get all sales for a business |
| `/sales/{business_id}/{sale_id}` | GET | Get a single sale |
| `/sales/{business_id}/{sale_id}` | PUT | Update a sale |
| `/sales/{business_id}/{sale_id}` | DELETE | Delete a sale |

---

## Approvals

| Endpoint | Method | Description |
|---|---|---|
| `/approvals/send_approval` | POST | Send a business join approval request (default pending) |
| `/approvals/get_approvals/{business_id}` | GET | Get all pending approvals for a business |
| `/approvals/confirm_approvals/{business_id}` | POST | Confirm approvals (approve/reject) |

---
## Customers

| Endpoint | Method | Description |
|---|---|---|
| `/customers/{business_id}` | POST | Create a new customer account|
| `/customers/{business_id}/` | GET | Get all customers in the business|


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
uvicorn app.main:app --reload
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

## Author

**Addy Samuel**  
Backend Engineer — building for African markets  
[GitHub](https://github.com/AJ-190) · [LinkedIn](https://linkedin.com/in/your-profile)

---

## License

This project is licensed under the MIT License.




