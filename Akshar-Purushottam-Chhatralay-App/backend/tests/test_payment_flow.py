"""Run with: pip install httpx; python -m unittest discover -s tests"""
import os
import re
import tempfile
import unittest
from pathlib import Path

DB_DIR = tempfile.TemporaryDirectory()
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(DB_DIR.name) / "app.db")
os.environ["SECRET_KEY"] = "test-only-key"
os.environ["ADMIN_EMAIL"] = "admin@example.com"
os.environ["ADMIN_PASSWORD"] = "test-admin-password"
os.environ["RESEND_API_KEY"] = "test-only-key"
os.environ["EMAIL_FROM"] = "no-reply@example.com"

from fastapi.testclient import TestClient
from app import main


class PaymentFlow(unittest.TestCase):
    def test_calendar_year_archiving_and_email_verification(self):
        sent = []
        main.send_email = lambda recipients, subject, body: sent.append((recipients, subject, body))
        with TestClient(main.app) as client:
            login = client.post("/api/auth/login", data={"username":"admin@example.com","password":"test-admin-password"})
            admin = {"Authorization":"Bearer "+login.json()["access_token"]}
            created = client.post("/api/admin/tenants", headers=admin, json={"full_name":"Calendar Tenant",
                "email":"calendar@example.com","room":"C1","move_in_date":"2027-01-01","weekly_rent":100})
            self.assertEqual(created.status_code,200,created.text)
            tenant_id = created.json()["id"]
            invalid = client.post("/api/auth/register",json={"full_name":"Calendar Tenant","email":"calendar@example.com",
                "password":"tenant-password","invite_code":"wrong"})
            self.assertEqual(invalid.status_code,403)
            row = next(t for t in client.get("/api/admin/tenants",headers=admin).json() if t["id"]==tenant_id)
            self.assertFalse(row["registered"])
            code = re.search(r"code is: (\S+)", next(body for _,subject,body in sent if subject=="Your chhatralay registration code")).group(1)
            registered = client.post("/api/auth/register",json={"full_name":"Calendar Tenant","email":"calendar@example.com",
                "password":"tenant-password","invite_code":code})
            self.assertEqual(registered.status_code,200,registered.text)
            tenant = {"Authorization":"Bearer "+registered.json()["access_token"]}
            charge = client.post("/api/admin/charges",headers=admin,json={"tenant_id":tenant_id,"due_date":"2027-12-31","amount":100})
            charge_id = charge.json()["id"]
            self.assertEqual(client.post(f"/api/admin/tenants/{tenant_id}/archive",headers=tenant).status_code,403)
            self.assertEqual(client.post(f"/api/admin/tenants/{tenant_id}/archive",headers=admin).status_code,409)
            submitted = client.post("/api/payments",headers=tenant,data={"amount":"60.00","payment_date":"2027-12-31","bank_reference":"CAL-1"})
            self.assertEqual(submitted.status_code,200,submitted.text)
            self.assertEqual(client.post(f"/api/admin/tenants/{tenant_id}/archive",headers=admin).status_code,409)
            approved = client.post(f"/api/admin/payments/{submitted.json()['id']}/review",headers=admin,json={"decision":"approved"})
            self.assertEqual(approved.status_code,200,approved.text)
            manual = client.patch(f"/api/admin/charges/{charge_id}",headers=admin,json={"amount_paid":100,"payment_date":"2028-01-01"})
            self.assertEqual(manual.status_code,200,manual.text)
            totals_2027 = client.get("/api/admin/collections?year=2027",headers=admin).json()
            totals_2028 = client.get("/api/admin/collections?year=2028",headers=admin).json()
            self.assertEqual(next(t["collected"] for t in totals_2027["tenants"] if t["tenant_id"]==tenant_id),60)
            self.assertEqual(next(t["collected"] for t in totals_2028["tenants"] if t["tenant_id"]==tenant_id),40)
            self.assertEqual(client.get("/api/admin/collections?year=2027",headers=tenant).status_code,403)
            self.assertEqual(client.post(f"/api/admin/tenants/{tenant_id}/archive",headers=admin).status_code,200)
            self.assertEqual(client.get("/api/me/profile",headers=tenant).status_code,401)
            self.assertEqual(client.post(f"/api/admin/tenants/{tenant_id}/restore",headers=admin).status_code,200)
            self.assertEqual(client.get("/api/me/profile",headers=tenant).status_code,200)

    def test_bulk_charges_and_tenant_details(self):
        sent = []
        main.send_email = lambda recipients, subject, body: sent.append((recipients, subject, body))
        with TestClient(main.app) as client:
            login = client.post("/api/auth/login", data={"username": "admin@example.com", "password": "test-admin-password"})
            self.assertEqual(login.status_code, 200, login.text)
            admin = {"Authorization": "Bearer " + login.json()["access_token"]}
            ids = []
            for number, rent in ((1, 125), (2, 175)):
                response = client.post("/api/admin/tenants", headers=admin, json={
                    "full_name": f"Bulk Tenant {number}", "email": f"bulk{number}@example.com", "phone": "0400000000",
                    "current_address": "Perth", "room": str(number), "move_in_date": "2026-01-01",
                    "weekly_rent": rent, "reference_name": "Ref Person"})
                self.assertEqual(response.status_code, 200, response.text)
                ids.append(response.json()["id"])
            self.assertEqual(client.get(f"/api/admin/tenants/{ids[0]}").status_code, 401)
            details = client.get(f"/api/admin/tenants/{ids[0]}", headers=admin)
            self.assertEqual(details.json()["reference_name"], "Ref Person")
            self.assertEqual(details.json()["current_address"], "Perth")
            charge = client.post("/api/admin/charges/all", headers=admin, json={"due_date": "2026-12-01"})
            self.assertEqual(charge.status_code, 200, charge.text)
            self.assertEqual(charge.json()["created"], 2)
            self.assertEqual(client.post("/api/admin/charges/all", headers=admin, json={"due_date": "2026-12-01"}).status_code, 409)
            self.assertEqual([client.get(f"/api/admin/tenants/{i}", headers=admin).json()["charges"][0]["amount"] for i in ids], [125, 175])
            self.assertTrue(any(subject == "Rent due on 2026-12-01" for _, subject, _ in sent))

    def test_review_and_receipt_permissions(self):
        sent = []
        main.send_email = lambda recipients, subject, body: sent.append((recipients, subject, body))
        with TestClient(main.app) as client:
            response = client.post("/api/auth/login", data={"username": "admin@example.com", "password": "test-admin-password"})
            self.assertEqual(response.status_code, 200, response.text)
            admin = {"Authorization": "Bearer " + response.json()["access_token"]}
            created = client.post("/api/admin/tenants", headers=admin, json={
                "full_name": "Example Tenant", "email": "tenant@example.com", "room": "A1",
                "move_in_date": "2026-01-01", "weekly_rent": 200})
            self.assertEqual(created.status_code, 200, created.text)
            tenant_id = created.json()["id"]
            invite = next(body for _, subject, body in sent if subject == "Your chhatralay registration code")
            code = re.search(r"code is: (\S+)", invite).group(1)
            self.assertEqual(client.post("/api/auth/register", json={"full_name": "Other", "email": "tenant@example.com", "password": "some-password", "invite_code": "wrong"}).status_code, 403)
            registered = client.post("/api/auth/register", json={"full_name": "Example Tenant", "email": "tenant@example.com", "password": "some-password", "invite_code": code})
            self.assertEqual(registered.status_code, 200, registered.text)
            tenant = {"Authorization": "Bearer " + registered.json()["access_token"]}
            self.assertEqual(client.get("/api/admin/tenants", headers=tenant).status_code, 403)
            self.assertEqual(client.get(f"/api/admin/tenants/{tenant_id}", headers=tenant).status_code, 403)
            self.assertEqual(client.get("/api/me/profile", headers=admin).status_code, 403)
            self.assertEqual(client.get("/api/me/profile", headers=tenant).json()["id"], tenant_id)
            self.assertIn("Example Tenant", [t["name"] for t in client.get("/api/admin/tenants", headers=admin).json()])
            self.assertEqual(client.post("/api/admin/charges", headers=admin, json={"tenant_id": tenant_id, "due_date": "2026-02-01", "amount": 100}).status_code, 200)
            claim = client.post("/api/payments", headers=tenant,
                data={"amount": "60.00", "payment_date": "2026-02-01", "bank_reference": "ABC123"},
                files={"receipt": ("proof.png", b"\x89PNG\r\n\x1a\n" + b"small-test-image", "image/png")})
            self.assertEqual(claim.status_code, 200, claim.text)
            payment_id = claim.json()["id"]
            self.assertEqual(claim.json()["state"], "pending")
            self.assertEqual(client.get("/api/me", headers=tenant).json()["tenant"]["balance"], 100)
            self.assertEqual(client.get(f"/api/admin/payments/{payment_id}/receipt", headers=tenant).status_code, 403)
            self.assertEqual(client.get(f"/api/admin/payments/{payment_id}/receipt", headers=admin).status_code, 200)
            self.assertEqual(client.post(f"/api/admin/payments/{payment_id}/review", headers=admin, json={"decision": "approved"}).status_code, 200)
            self.assertEqual(client.get("/api/me", headers=tenant).json()["tenant"]["balance"], 40)
            self.assertEqual(client.post(f"/api/admin/payments/{payment_id}/review", headers=admin, json={"decision": "approved"}).status_code, 409)
            rejected = client.post("/api/payments", headers=tenant, data={"amount": "20.00", "payment_date": "2026-02-02", "bank_reference": "DEF456"})
            self.assertEqual(rejected.status_code, 200, rejected.text)
            self.assertEqual(client.post(f"/api/admin/payments/{rejected.json()['id']}/review", headers=admin, json={"decision": "rejected", "note": "Not in bank"}).status_code, 200)
            self.assertEqual(client.get("/api/me", headers=tenant).json()["tenant"]["balance"], 40)
            self.assertTrue(any("Payment approved" == subject for _, subject, _ in sent))
            self.assertTrue(any("Payment rejected" == subject for _, subject, _ in sent))


if __name__ == "__main__":
    unittest.main()
