# PG Management Web Application

A responsive (mobile + desktop) PG management web app with 3 roles:
- **Admin**: approves manager/customer accounts, sees reports.
- **Manager/Owner**: creates PG structure (PG → floors/flats → rooms), admits/exits tenants, creates monthly invoices, configures payment settings (MFA protected).
- **Customer**: logs in using email/mobile/username and pays rent.

## Features implemented
- Multi-role authentication and authorization.
- Approval flow for registrations.
- Dynamic hierarchy: Country → City → PG → Flat → Room.
- Dynamic room sharing + bed rent (single / two_share / three_share).
- Customer profile with permanent address, emergency contact, company, food option, deposit.
- Monthly rent generation with optional food charge.
- Payment flow:
  - Mobile: UPI deep-link (`upi://pay?...`) to switch to UPI apps.
  - Desktop: Manager QR image URL + bank account + IFSC shown.
- MFA gate for manager payment settings updates.
- Reports: new customers in current month + paid rents.

## Tech stack
- Python 3.11+
- Flask + Flask-Login + Flask-SQLAlchemy
- SQLite (local dev)
- Bootstrap responsive UI

## Local setup
1. Create virtual env and install deps
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Run app
   ```bash
   python app.py
   ```
3. Open `http://127.0.0.1:5000`
4. Default admin:
   - username: `admin`
   - password: `admin123`

## Cloud database options

### 1) Free/low-cost PostgreSQL (recommended)
- **Neon**: free tier available; paid starts around ~$19/month depending on usage.
- **Supabase Postgres**: free tier available; paid plans start around ~$25/month.
- **Railway Postgres**: usage-based; often low-cost starter usage.

> Check current pricing on provider sites because prices can change.

### How to switch from SQLite to Cloud Postgres
1. Create DB on Neon/Supabase/Railway.
2. Copy connection string (example):
   `postgresql+psycopg2://user:password@host/dbname`
3. Install postgres driver:
   ```bash
   pip install psycopg2-binary
   ```
4. Update config in `app.py`:
   ```python
   app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql+psycopg2://...'
   ```
5. Run schema creation (or Flask-Migrate in production):
   ```bash
   python app.py
   ```

## Payment gateway integration (production note)
Current app uses demo “mark paid” flow. In production, integrate Razorpay/Stripe/PayU APIs:
- Create order from manager invoice.
- Redirect or SDK popup.
- Verify payment signature on callback/webhook.
- Mark invoice paid only after verification.

## User Manual

### Admin
1. Login as admin.
2. Open Dashboard.
3. Approve pending managers/customers.
4. Open Reports to view monthly new customers and paid invoices.

### Manager / PG Owner
1. Register as manager and wait admin approval.
2. Login, complete MFA when accessing payment settings.
3. Create PG (country/city/address/food charge).
4. Add flats and rooms dynamically with share type and rent per bed.
5. Configure UPI ID, bank account, IFSC, QR URL.
6. Admit customer (create account + assign PG/room + deposit + food option).
7. Create monthly invoices.
8. Use reports for monthly tracking.

### Customer
1. Register (or manager creates account) and wait approval.
2. Login with username/email/mobile.
3. See monthly invoices on dashboard.
4. Click Pay:
   - Mobile opens UPI app via deep link.
   - Desktop shows QR/bank details.
5. Confirm payment (demo button).

## Security recommendations for real deployment
- Store secrets in environment variables.
- Use true OTP/TOTP MFA (Authy/Google Authenticator) instead of demo code.
- Enforce HTTPS + secure cookies.
- Add audit logs for payment setting changes.
- Add webhook-based payment verification.

