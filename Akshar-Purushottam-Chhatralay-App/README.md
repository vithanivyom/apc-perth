# Akshar Purushottam Chhatralay

React frontend, FastAPI backend and PostgreSQL database. This update preserves existing tenant records and adds the requested features.

## Features

- Admin downloads a private CSV with **active and archived tenants**, their personal details, rent totals and outstanding balances. CSV cells are protected against spreadsheet formula injection.
- Admin sees each tenant's choice, including **Not voted**, beneath each activity poll. Tenants see only their own vote.
- Sessions close after **15 minutes without mouse, keyboard, touch or scrolling**. While active, the frontend renews a 15-minute server token.
- Registration uses a **six-digit email code** valid for 15 minutes. Five wrong attempts lock that code; admin can resend after one minute.
- Every email includes a website link. Admin can email one tenant from **Tenants → name → Send personal email**.
- Activities and rent charges email a calendar attachment (`.ics`) containing a one-day alert. Tenants must **open or accept the invitation** in their calendar app; the website cannot insert an event into a private calendar without permission.
- A separately configured daily job emails tenants **one day before an activity or unpaid rent charge**, using the Australia/Perth time zone. Sent reminders are recorded to avoid duplicates on retries.
- Tenant profile: name, mobile, date of birth, parent's mobile, home address, arrival date, university, course, graduation month/year, referee name/contact/location. Email and weekly rent remain necessary for sign-in and billing. Existing room and bond data are preserved.
- Previous functionality remains: payment submissions, receipt images, admin approval, archive only after full payment, collection reports and additional notification recipients.

## Update the existing GitHub + Render + Neon deployment

**Back up Neon before deploying.** Startup adds missing columns and creates the new reminder table; existing tenant, rent and payment records are preserved. Do not reset the database.

1. In your Mac's existing `apc-perth` Git checkout, replace the existing app files with the corresponding files from this ZIP. Keep the same backend/frontend directory layout. If the current project is nested inside `Akshar-Purushottam-Chhatralay-App/`, copy this ZIP's **contents** into that folder. Put `.github/workflows/reminders.yml` at the **Git repository root**, not inside the nested app folder.
2. Check `git status` and commit/push the code to `main`. Never commit `.env`, Neon passwords, Resend API keys, or secrets.
3. Render **backend Web Service**: retain your working `DATABASE_URL`, `SECRET_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `FRONTEND_URLS`, `RESEND_API_KEY`, and `EMAIL_FROM`. `FRONTEND_URLS` should contain the real tenant frontend, currently `https://apc-perth-sj8u.onrender.com`. Add `PUBLIC_FRONTEND_URL=https://apc-perth-sj8u.onrender.com` for email links. Add `REMINDER_SECRET` using a new value from `openssl rand -hex 32`. Save and redeploy; check `https://apc-perth.onrender.com/api/health` displays `{"status":"ok"}`.
4. Render **frontend Static Site**: set `VITE_API_URL=https://apc-perth.onrender.com`, which is the backend. Rebuild the frontend. Keep the Resend and reminder secrets out of the frontend.
5. GitHub repository → **Settings → Secrets and variables → Actions → New repository secret**: `APC_BACKEND_URL=https://apc-perth.onrender.com`; `REMINDER_SECRET` must match the private value from your Render backend. Enable repository Actions and keep `.github/workflows/reminders.yml` on `main`. The daily job runs at approximately **8:15 am Perth time**; scheduled Actions can run late. You can test with **Actions → Send rent and activity reminders → Run workflow**, which succeeds even if zero items are due tomorrow. Check Actions history for failures.
6. As admin, download CSV and post a poll. As a tenant, register with the emailed code and vote. Return as admin to check individual choices. Send a personal message; add a future activity or rent charge; confirm the email has the frontend link and `.ics` attachment. Sign out and test idle expiry.

**Email delivery:** `EMAIL_FROM` must be on a verified Resend sending domain. Normal app actions queue email after saving and log delivery failures in Render; a successful API response alone does not guarantee delivery. The daily reminder endpoint reports failures to GitHub Actions and records successful sends to avoid duplicates. If an event is added less than one day before it occurs, tenants still get its initial notice.

## Local Docker setup

1. Install Docker Desktop. Copy `.env.example` to `.env`.
2. Enter your admin details, Resend credentials if using email, and two distinct random values for `SECRET_KEY` and `REMINDER_SECRET`.
3. In this folder run `docker compose up --build`; open `http://localhost:5173`. API docs: `http://localhost:8000/docs`.

Local calendar invitations link to `http://localhost:5173`; use `PUBLIC_FRONTEND_URL` in production. Daily reminders require the included scheduled GitHub Actions workflow or another daily HTTPS scheduler that calls `/api/internal/send-reminders` using `Authorization: Bearer <REMINDER_SECRET>`. Starting Docker alone does not schedule reminders.

## Records and limitations

**Tenants → name → Remove tenant** archives a tenant after all charges are paid and no payment submission is pending. Archived accounts cannot sign in but stay in CSV and collections and can be restored. Already registered accounts remain usable; prior registrations have no retroactive verification record. Only new registrations need the six-digit code.

Collections cover 1 January through 31 December. Historical manual payments with no recorded payment date appear separately as undated instead of being assigned to a guessed year. Receipt images are private in PostgreSQL and capped at 2 MB; back up Neon and watch storage. Tenant password recovery and guaranteed email delivery require additional services. Rotate any Neon password shared in a message, then update `DATABASE_URL` in Render.
