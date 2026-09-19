# Akshar Purushottam Chhatralay

## Latest features

- Each resident profile has a unique number and allocated seva. Residents can sign in with either the unique number or email.
- Password recovery uses a six-digit code sent to the account email.
- Admins can download an on-demand PDF summary for a selected January-to-December year. The PDF is not stored in PostgreSQL.
- Rent payment submissions use bank transaction details only; new receipt images are not uploaded.
- Admin-only profiles are excluded from resident dashboards, tenant exports, collections, voting participation and PDF summaries. They receive routine email only when a payment is approved (account verification, password recovery and explicitly addressed messages still work).
- Detailed payment rows older than 365 days are consolidated by the existing scheduled cleanup, preserving yearly collection totals while reducing database storage.

React frontend, FastAPI backend and PostgreSQL database. This update preserves existing tenant records and adds the requested features.

## Features

- Admin downloads a private CSV with **active and archived tenants**, their personal details, rent totals and outstanding balances. CSV cells are protected against spreadsheet formula injection.
- Upcoming activities show their details and poll. After the activity date passes in Perth, tenants see only a short record of activities they voted on (activity date, selected option and vote date). Admins see a compact poll tally and can expand each summary to see each tenant's choice, including **Not voted**. Voting closes after the activity date.
- Before a tenant registers, admins can correct a mistyped email under **Tenants → tenant name → Correct email address**. Saving invalidates any earlier registration code and queues a new six-digit code for the corrected address. Registered accounts cannot have their login email changed through this form.
- Sessions close after **15 minutes without mouse, keyboard, touch or scrolling**. While active, the frontend renews a 15-minute server token.
- Registration uses a **six-digit email code** valid for 15 minutes. Five wrong attempts lock that code; admin can resend after one minute.
- Every email includes a website link. Admin can email one tenant from **Tenants → name → Send personal email**.
- Activities and rent charges email a calendar attachment (`.ics`) containing a one-day alert. Tenants must **open or accept the invitation** in their calendar app; the website cannot insert an event into a private calendar without permission.
- A separately configured daily job emails tenants **one day before an activity or unpaid rent charge**, using the Australia/Perth time zone. Sent reminders are recorded to avoid duplicates on retries.
- Tenant profile: name, mobile, date of birth, parent's mobile, home address, arrival date, university, course, graduation month/year, referee name/contact/location. Email and weekly rent remain necessary for sign-in and billing. Existing room and bond data are preserved.
- Previous functionality remains: payment submissions, receipt images, admin approval, archive only after full payment, collection reports and additional notification recipients.
- Admin can upload a JPG/PNG/WebP profile photo (maximum 1 MB) on a new profile or the Tenants detail page. Photos are stored privately in Neon and shown only to that person and admins.
- New profiles choose **Tenant only**, **Admin only**, or **Tenant and admin** before sending the registration code. Admin-only accounts cannot pay rent or vote and are excluded from bulk charges; combined accounts can manage tenants and make their own payments, but cannot review their own payments.
- A daily cleanup removes payment submissions, bank references, and receipt images more than 365 days after submission, along with old manual payment rows. Rent charges and balances remain; a compact annual amount per tenant preserves collections totals. Pending requests older than 365 days also disappear.

## Update the existing GitHub + Render + Neon deployment

**Back up Neon before deploying.** Startup adds missing columns and creates the new reminder and annual-summary tables; existing tenant, rent and payment records are preserved on deployment. The daily cleanup later deletes detailed payment history older than 365 days. Do not reset the database.

1. In your Mac's existing `apc-perth` Git checkout, replace the existing app files with the corresponding files from this ZIP. Keep the same backend/frontend directory layout. If the current project is nested inside `Akshar-Purushottam-Chhatralay-App/`, copy this ZIP's **contents** into that folder. Put `.github/workflows/reminders.yml` at the **Git repository root**, not inside the nested app folder.
2. Check `git status` and commit/push the code to `main`. Never commit `.env`, Neon passwords, Resend API keys, or secrets.
3. Render **backend Web Service**: retain your working `DATABASE_URL`, `SECRET_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `FRONTEND_URLS`, `RESEND_API_KEY`, and `EMAIL_FROM`. `FRONTEND_URLS` should contain the real tenant frontend, currently `https://apc-perth-sj8u.onrender.com`. Add `PUBLIC_FRONTEND_URL=https://apc-perth-sj8u.onrender.com` for email links. Add `REMINDER_SECRET` using a new value from `openssl rand -hex 32`. Save and redeploy; check `https://apc-perth.onrender.com/api/health` displays `{"status":"ok"}`.
4. Render **frontend Static Site**: set `VITE_API_URL=https://apc-perth.onrender.com`, which is the backend. Rebuild the frontend. Keep the Resend and reminder secrets out of the frontend.
5. GitHub repository → **Settings → Secrets and variables → Actions → New repository secret**: `APC_BACKEND_URL=https://apc-perth.onrender.com`; `REMINDER_SECRET` must match the private value from your Render backend. Enable repository Actions and keep `.github/workflows/reminders.yml` on `main`. The daily job runs at approximately **8:15 am Perth time**; scheduled Actions can run late. The same job now **deletes old payment details** each day. Before deploying the updated workflow, export and securely back up any payment records you need to retain. You can test with **Actions → Send rent and activity reminders → Run workflow**; it will send due reminders and delete all eligible old payment rows immediately. Check Actions history for failures.
6. As admin, download CSV and post a poll. As a tenant, register with the emailed code and vote. Return as admin to check individual choices. Send a personal message; add a future activity or rent charge; confirm the email has the frontend link and `.ics` attachment. Sign out and test idle expiry.

**Email delivery:** `EMAIL_FROM` must be on a verified Resend sending domain. Normal app actions queue email after saving and log delivery failures in Render; a successful API response alone does not guarantee delivery. The daily reminder endpoint reports failures to GitHub Actions and records successful sends to avoid duplicates. If an event is added less than one day before it occurs, tenants still get its initial notice.

## Local Docker setup

1. Install Docker Desktop. Copy `.env.example` to `.env`.
2. Enter your admin details, Resend credentials if using email, and two distinct random values for `SECRET_KEY` and `REMINDER_SECRET`.
3. In this folder run `docker compose up --build`; open `http://localhost:5173`. API docs: `http://localhost:8000/docs`.

Local calendar invitations link to `http://localhost:5173`; use `PUBLIC_FRONTEND_URL` in production. Daily reminders require the included scheduled GitHub Actions workflow or another daily HTTPS scheduler that calls `/api/internal/send-reminders` using `Authorization: Bearer <REMINDER_SECRET>`. Starting Docker alone does not schedule reminders.

## Records and limitations

**Tenants → name → Remove tenant** archives a tenant after all charges are paid and no payment submission is pending. Archived accounts cannot sign in but stay in CSV and collections and can be restored. Already registered accounts remain usable; prior registrations have no retroactive verification record. Only new registrations need the six-digit code.

Collections cover 1 January through 31 December. Historical manual payments with no recorded payment date appear separately as undated instead of being assigned to a guessed year. New payment submissions do not accept receipt images. The retention job uses the **submission/recorded timestamp**, not the entered payment date, and leaves annual totals and rent balances but permanently removes transaction-level details older than 365 days. Export any legally required detailed records before cleanup. [Australian government guidance](https://business.gov.au/finance/payments-and-invoicing/record-keeping) says most business transaction records must be kept for five years; check which rules apply to this house and keep a separate secure archive where required. PostgreSQL storage may shrink only after vacuum and Neon space reclamation. Password recovery requires working Resend settings; no email provider can guarantee delivery. Rotate any Neon password shared in a message, then update `DATABASE_URL` in Render.
