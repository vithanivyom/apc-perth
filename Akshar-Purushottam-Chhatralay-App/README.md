# Akshar Purushottam Chhatralay — PostgreSQL housing app

A complete starter with a React frontend, FastAPI backend and PostgreSQL database.

## Features

- Admin and tenant accounts with JWT authentication
- Admin-only tenant, references, address and rent management
- Tenant-only personal balance and rent history
- Admin view of every pending balance
- Admin view of all tenants and their outstanding balances
- Admin-only personal details, references, charge history, and payment history for each tenant
- Dedicated admin **Tenants** page listing all tenant names, including inactive records; selecting a name opens that tenant's details
- Tenant **My details** page showing only the signed-in tenant's saved profile, references, rent charges, and payment submissions
- Create rent charges for every active tenant on one due date using each tenant's saved weekly rent; email notices are queued for each tenant
- Tenant payment submissions with optional private receipt image (JPG, PNG, WebP, max 2 MB)
- Admin approval or rejection; balance updates only on approval; duplicate bank references rejected per tenant
- Email notices for new tenant accounts, rent charges, payment submissions and decisions, poll votes, and activities
- Admin-managed additional email recipients and one-time email registration codes
- White and red mobile layout with compact navigation and phone-friendly forms
- Archive a tenant only when their rent is paid in full and there are no pending payment submissions; archived accounts cannot sign in, can be restored, and retain their payment history
- Admin collections by tenant for each January 1 through December 31 period, including approved submissions and dated manual payment adjustments
- Activities and polls
- One vote per tenant per poll
- Poll totals visible to the admin; tenants see only their own choice
- PostgreSQL constraints and server-side role checks

## Run it locally

1. Install Docker Desktop.
2. Open docker-compose.yml.
3. Copy `.env.example` to `.env` and configure all values, especially `SECRET_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `RESEND_API_KEY`, and `EMAIL_FROM`.
4. Open a terminal in this folder.
5. Run: docker compose up --build
6. Open http://localhost:5173
7. Sign in using the admin email and password from docker-compose.yml.

API documentation: http://localhost:8000/docs

## First-use workflow

1. Admin signs in.
2. Admin opens Add tenant and saves the tenant using their real email.
3. Admin adds a rent charge from the dashboard.
4. Tenant opens the website and selects Create your account.
5. The tenant must register with the exact email and one-time code sent by the app (valid for seven days). The admin can resend it from the dashboard.
6. Tenant can see only their own balance, activities and polls.

## Important production changes

- Never use the sample passwords or secret in production.
- Use HTTPS and a managed PostgreSQL service.
- Restrict FRONTEND_URLS to the real frontend domain.
- Add automated database backups.
- Use database migrations (Alembic) before changing a live schema.
- Use secure, HTTP-only cookies instead of browser storage for a high-security deployment.
- Add a password-reset email flow before inviting tenants who might forget their passwords.
- Tenant registration now requires a one-time code sent to the address on the tenant record. Configure the Resend Email API before creating more tenant accounts.
- Receipt bytes are stored in Neon PostgreSQL to avoid losing files when Render restarts. Each image is capped at 2 MB. Monitor your Neon storage usage and move files to private object storage as usage grows.
- Email sends happen after the database change. Failed email delivery is logged but is not retried automatically; use a durable mail queue or provider webhooks for delivery guarantees.
- Never send bank passwords or full account credentials in the payment details field. A submitted receipt is a claim, not bank verification.
- Review the privacy policy and Australian privacy obligations before collecting personal data.

## Suggested deployment

- Frontend: Vercel, Netlify or Cloudflare Pages
- Backend: Render, Railway, Fly.io or Azure App Service
- PostgreSQL: Neon, Supabase, Render PostgreSQL, Railway or Azure Database for PostgreSQL

When deploying, set VITE_API_URL to the backend URL, FRONTEND_URLS to the frontend URL, and DATABASE_URL to the managed PostgreSQL connection string.

## Updating the existing Neon + Render deployment

1. Back up the production database using Neon's backup/export tools. Do not replace or reset the database.
2. Set up a Resend account, verify a domain you own, and create a sending API key. [Resend's email API](https://resend.com/docs/api-reference/emails/send-email) sends over HTTPS. Add `RESEND_API_KEY` and `EMAIL_FROM` (for example, `Chhatralay <updates@your-verified-domain.example>`) to the **backend Web Service** in Render. Render's Free web services [block outbound SMTP ports](https://render.com/docs/free), so standard SMTP will not work here. The testing sender may only email your own address until a domain is verified. Keep your existing `DATABASE_URL`, `SECRET_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `FRONTEND_URLS` unchanged unless intentionally rotating them. Do not add the API key to the frontend or GitHub.
3. Replace the tracked project files in your Git checkout with the corresponding files from this ZIP, inspect `git diff`, commit, and push `main`. Deploy backend first. On startup, SQLAlchemy creates only the new `payment_submissions`, `notification_recipients`, and `registration_invites` tables; existing tables and tenants are retained. For later schema changes use a real database migration.
4. Wait for backend `https://apc-perth.onrender.com/api/health` to respond with `{"status":"ok"}`, then wait for the frontend Static Site to build and become Live. Keep `VITE_API_URL=https://apc-perth.onrender.com` on that frontend.
5. Test one tenant with a small rent charge: submit a payment and image, confirm status Pending and no balance change, approve it, and check the balance changes once. Submit another and reject it; confirm the balance stays unchanged. Confirm mail reaches tenant, admin, and any additional recipient. Test an activity announcement. The backend receipt endpoint requires admin authentication.

Existing unregistered tenants need a registration code: sign in as admin and click **Email code** beside their name. Existing registered tenants can keep logging in. Do not publish this update before the email API and sender domain are configured if tenants still need to register.

### Bulk rent workflow

Open **Tenants** in the admin menu and click a name to see the tenant's address, reference contacts, bond, charge history, and payment submissions. Tenants see their own saved information under **My details**. The admin dashboard's **Charge all active tenants** action creates one charge per currently active tenant using each person's saved weekly rent, and queues email notices after saving. The same due date cannot be submitted through this bulk form twice. This action does not charge a bank account or send future recurring reminders automatically; repeat it for the next rent period. Individual charges remain available for adjustments. Ensure `EMAIL_FROM` uses your verified Resend domain before relying on email notifications; the backend will log failed deliveries.

### Tenant removal and annual collections

**Tenants → tenant name → Remove tenant** is enabled only after every charge is paid and all submitted payments have been reviewed. The backend repeats these checks. Removal archives the tenant instead of deleting records, disables their login, and excludes them from future bulk charges. Use **Show archived → Restore tenant** to reactivate them. Archived tenants remain in financial reports.

**Collections** shows money received from 1 January of the selected year up to, but excluding, 1 January of the next year. It uses the payment date entered by the tenant for approved submissions, plus the payment date on any manual admin payment adjustment made after this update. Earlier manual payments have no recorded payment date; the report shows them separately as **historical undated** instead of assigning them to a guessed year. Pending or rejected submissions are not counted. If manually recording a payment through the API, provide `payment_date` in the `PATCH /api/admin/charges/{charge_id}` JSON along with `amount_paid`; if omitted, today's server date is used.

New tenant registration requires a one-time code emailed to the exact tenant email already entered by the admin. Incorrect or expired codes do not create an account and do not change the Registered status. Previously registered accounts continue to work; the app does not have independent verification records for accounts created before this requirement.

On deployment the backend creates the new `manual_payments` table without changing the existing `tenants` or `rent_charges` tables. Back up the Neon database before deploying. No new Render environment variables are needed.

The existing `docker-compose.yml` in the uploaded ZIP included a real admin password and JWT key. This revision removes them; rotate any values that were committed to GitHub or shared. **Changing `ADMIN_PASSWORD` in Render does not change the password of an existing admin account**: sign in and use **Email recipients → Change admin password** after deploying. Also rotate `SECRET_KEY` in Render, which signs users out. Removing a password from the current file does not remove it from Git history.

## Folder guide

- frontend/src/App.jsx — screens and frontend behaviour
- frontend/src/style.css — design and mobile layout
- backend/app/main.py — database models, authentication and API
- docker-compose.yml — starts frontend, backend and PostgreSQL together
