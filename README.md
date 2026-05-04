# Smart Sales & Inventory AI Tracking System

A production-ready REST API for small businesses to manage inventory, track sales, and receive automated performance reports — built with FastAPI and PostgreSQL.

---

##  Live API

**Base URL:** `https://smart-sales-inventory.onrender.com`  
**Interactive Docs:** `https://smart-sales-inventory.onrender.com/docs`

---

## ✨ Features

- **Authentication** — User registration and login secured with JWT
- **Multi-Business Support** — One user can own and manage multiple businesses
- **Product Management** — Full CRUD operations on products per business
- **Sales Tracking** — Record, retrieve, update, and delete sales transactions with automatic calculations
- **Automated Reports** — Daily, weekly, and monthly sales summaries sent via email to admins and managers using background cron jobs

---

##  Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI |
| Database | PostgreSQL |
| Auth | JWT (OAuth2) |
| Background Jobs | APScheduler / Cron |
| Email | SMTP |
| Deployment | Render |

---

##  Project Structure

```
buissness-bot-v1/
├── sales_tracker/
│   └── app/
│       ├── main.py          # App entry point, router registration
│       ├── models.py        # Database models
│       ├── schemas.py       # Pydantic schemas
│       ├── database.py      # DB connection
│       ├── oauth2.py        # JWT auth logic
│       ├── utils.py         # Helper functions
│       ├── routers/         # Route handlers
│       └── core/
│           └── config.py    # Environment config
├── alembic/                 # Database migrations
├── render.yaml              # Render deployment config
├── requirements.txt
└── .env                     # Environment variables (not committed)
```

---

## 🔐 Authentication

All protected routes require a Bearer token in the `Authorization` header.

```
Authorization: Bearer <your_token>
```

| Endpoint | Method | Description |
|---|---|---|
| `/auth/register` | POST | Create a new user account |
| `/auth/login` | POST | Login and receive JWT token |

---

## 🏢 Businesses

| Endpoint | Method | Description |
|---|---|---|
| `/businesses` | POST | Create a new business |
| `/businesses` | GET | Get all businesses for current user |
| `/businesses/{id}` | GET | Get a single business |
| `/businesses/{id}` | PUT | Update a business |
| `/businesses/{id}` | DELETE | Delete a business |

---

##  Products

| Endpoint | Method | Description |
|---|---|---|
| `/businesses/{id}/products` | POST | Add a product to a business |
| `/businesses/{id}/products` | GET | Get all products for a business |
| `/businesses/{id}/products/{product_id}` | GET | Get a single product |
| `/businesses/{id}/products/{product_id}` | PUT | Update a product |
| `/businesses/{id}/products/{product_id}` | DELETE | Delete a product |

---

## 💰 Sales

| Endpoint | Method | Description |
|---|---|---|
| `/businesses/{id}/sales` | POST | Record a sale (auto-calculates totals) |
| `/businesses/{id}/sales` | GET | Get all sales for a business |
| `/businesses/{id}/sales/{sale_id}` | GET | Get a single sale |
| `/businesses/{id}/sales/{sale_id}` | PUT | Update a sale |
| `/businesses/{id}/sales/{sale_id}` | DELETE | Delete a sale |

---

## 📊 Automated Reports

Background cron jobs run on schedule and email reports to business admins and managers:

- **Daily** — End-of-day sales summary
- **Weekly** — Weekly performance overview
- **Monthly** — Monthly revenue and inventory report

---

## ⚙️ Environment Variables

Create a `.env` file in the project root:

```env
DATABASE_URL=postgresql://user:password@host/dbname
SECRET_KEY=your_secret_key
SUPER_ADMIN_EMAIL=admin@example.com
SUPER_ADMIN_APP_PASSWORD=your_email_app_password
SUPER_ADMIN_NAME=Admin Name
```

---

##  Running Locally

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
uvicorn sales_tracker.app.main:app --reload
```

---

## 📄 License

MIT
