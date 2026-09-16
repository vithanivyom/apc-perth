# Akshar Purushottam Chhatralay — PostgreSQL housing app

A complete starter with a React frontend, FastAPI backend and PostgreSQL database.

## Features

- Admin and tenant accounts with JWT authentication
- Admin-only tenant, references, address and rent management
- Tenant-only personal balance and rent history
- Admin view of every pending balance
- Activities and polls
- One vote per tenant per poll
- Poll totals visible to the admin; tenants see only their own choice
- PostgreSQL constraints and server-side role checks

## Run it locally

1. Install Docker Desktop.
2. Open docker-compose.yml.
3. Change ADMIN_EMAIL, ADMIN_PASSWORD, and SECRET_KEY.
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
5. The tenant must register with the exact email saved by the admin.
6. Tenant can see only their own balance, activities and polls.

## Important production changes

- Never use the sample passwords or secret in production.
- Use HTTPS and a managed PostgreSQL service.
- Restrict FRONTEND_URLS to the real frontend domain.
- Add automated database backups.
- Use database migrations (Alembic) before changing a live schema.
- Use secure, HTTP-only cookies instead of browser storage for a high-security deployment.
- Add email verification and password-reset email before serving real tenants.
- Review the privacy policy and Australian privacy obligations before collecting personal data.

## Suggested deployment

- Frontend: Vercel, Netlify or Cloudflare Pages
- Backend: Render, Railway, Fly.io or Azure App Service
- PostgreSQL: Neon, Supabase, Render PostgreSQL, Railway or Azure Database for PostgreSQL

When deploying, set VITE_API_URL to the backend URL, FRONTEND_URLS to the frontend URL, and DATABASE_URL to the managed PostgreSQL connection string.

## Folder guide

- frontend/src/App.jsx — screens and frontend behaviour
- frontend/src/style.css — design and mobile layout
- backend/app/main.py — database models, authentication and API
- docker-compose.yml — starts frontend, backend and PostgreSQL together
