"""Run with: python -m unittest discover -s backend/tests -v (using backend requirements)."""
import csv
import importlib.util
import io
import os
import re
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import json
import base64
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient


class FeatureFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        os.environ["DATABASE_URL"] = "sqlite:///" + cls.tmp.name + "/app.db"
        os.environ["SECRET_KEY"] = "test-secret-only"
        os.environ["ADMIN_EMAIL"] = "admin@example.com"
        os.environ["ADMIN_PASSWORD"] = "a-test-password"
        os.environ["RESEND_API_KEY"] = "test-resend-placeholder"
        os.environ["EMAIL_FROM"] = "Tester <admin@example.com>"
        os.environ["REMINDER_SECRET"] = "test-reminder-placeholder"
        # Mimic two tables already present in a live deployment. Startup must add
        # columns without dropping data or requiring an empty Neon database.
        db_path = cls.tmp.name + "/app.db"
        with sqlite3.connect(db_path) as connection:
            connection.execute("""CREATE TABLE tenants (id INTEGER PRIMARY KEY, user_id INTEGER UNIQUE,
                full_name VARCHAR(150) NOT NULL, email VARCHAR(255) NOT NULL UNIQUE,
                phone VARCHAR(40) NOT NULL, current_address TEXT NOT NULL,
                room VARCHAR(80) NOT NULL, move_in_date DATE NOT NULL,
                weekly_rent NUMERIC(10,2) NOT NULL, bond_amount NUMERIC(10,2) NOT NULL,
                reference_name VARCHAR(150) NOT NULL, reference_phone VARCHAR(40) NOT NULL,
                reference_email VARCHAR(255) NOT NULL, is_active BOOLEAN NOT NULL)""")
            connection.execute("""INSERT INTO tenants VALUES
                (100,NULL,'Existing Tenant','existing@example.com','','','',
                 '2025-01-01',100,0,'','','',1)""")
            connection.execute("""CREATE TABLE registration_invites
                (tenant_id INTEGER PRIMARY KEY, token_hash VARCHAR(64) NOT NULL,
                 expires_at DATETIME NOT NULL)""")
        spec = importlib.util.spec_from_file_location("apc_feature_test_main", Path(__file__).resolve().parents[1] / "app" / "main.py")
        cls.main = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.main)
        cls.emails = []
        cls.original_send_email = cls.main.send_email

        def record(recipients, subject, body, attachment=None):
            cls.emails.append((recipients, subject, body, attachment))
            return True

        cls.main.send_email = record
        cls.client = TestClient(cls.main.app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        cls.main.send_email = cls.original_send_email
        cls.tmp.cleanup()

    def test_registration_export_votes_and_reminders(self):
        login = self.client.post("/api/auth/login", data={"username": "admin@example.com", "password": "a-test-password"})
        self.assertEqual(login.status_code, 200, login.text)
        admin = {"Authorization": "Bearer " + login.json()["access_token"]}
        preserved = self.client.get("/api/admin/tenants/100", headers=admin)
        self.assertEqual(preserved.status_code, 200, preserved.text)
        self.assertEqual(preserved.json()["full_name"], "Existing Tenant")
        tomorrow = (datetime.now(ZoneInfo("Australia/Perth")) + timedelta(days=1)).date().isoformat()
        response = self.client.post("/api/admin/tenants", headers=admin, json={
            "full_name": "New Tenant", "email": "tenant@example.com", "move_in_date": "2025-01-01",
            "weekly_rent": 250, "graduation_month": "2027-11", "parent_phone": "0400000000"})
        self.assertEqual(response.status_code, 200, response.text)
        tenant_id = response.json()["id"]
        sent_code = next(message for message in self.emails if message[1] == "Your registration code")
        code = re.search(r"\b\d{6}\b", sent_code[2]).group()
        registration = self.client.post("/api/auth/register", json={"full_name": "New Tenant",
            "email": "tenant@example.com", "password": "a-secure-test-password", "invite_code": code})
        self.assertEqual(registration.status_code, 200, registration.text)
        tenant = {"Authorization": "Bearer " + registration.json()["access_token"]}

        csv_response = self.client.get("/api/admin/tenants/report.csv", headers=admin)
        self.assertEqual(csv_response.status_code, 200)
        rows = list(csv.DictReader(io.StringIO(csv_response.text.lstrip("\ufeff"))))
        self.assertEqual(next(row for row in rows if row["Name"] == "New Tenant")["Parent mobile"], "0400000000")
        self.assertEqual(self.client.get("/api/admin/tenants/report.csv", headers=tenant).status_code, 403)

        activity = self.client.post("/api/admin/activities", headers=admin, json={
            "title": "Dinner", "activity_date": tomorrow, "poll_question": "Coming?", "options": ["Yes", "No"]})
        self.assertEqual(activity.status_code, 200, activity.text)
        poll_activity = next(row for row in self.client.get("/api/activities", headers=admin).json() if row["id"]==activity.json()["id"])
        self.assertTrue(all(row["choice"] is None for row in poll_activity["poll"]["participation"]))
        poll_id = poll_activity["poll"]["id"]
        choice_id = poll_activity["poll"]["options"][0]["id"]
        self.assertEqual(self.client.post(f"/api/polls/{poll_id}/vote", headers=tenant,
            json={"option_id": choice_id}).status_code, 200)
        votes = next(row for row in self.client.get("/api/activities", headers=admin).json() if row["id"]==activity.json()["id"])["poll"]["participation"]
        self.assertEqual(next(row for row in votes if row["tenant_id"] == tenant_id)["choice"], "Yes")
        self.assertNotIn("participation", next(row for row in self.client.get("/api/activities", headers=tenant).json() if row["id"]==activity.json()["id"])["poll"])

        charge = self.client.post("/api/admin/charges/all", headers=admin, json={"due_date": tomorrow})
        self.assertEqual(charge.status_code, 200, charge.text)
        self.assertTrue(any(message[3] and message[3]["filename"].endswith(".ics") for message in self.emails))
        reminder_headers = {"Authorization": "Bearer test-reminder-placeholder"}
        self.assertEqual(self.client.post("/api/internal/send-reminders").status_code, 403)
        first = self.client.post("/api/internal/send-reminders", headers=reminder_headers)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()["sent"], 4)
        self.assertEqual(self.client.post("/api/internal/send-reminders", headers=reminder_headers).json()["sent"], 0)
        self.assertEqual(self.client.post(f"/api/admin/tenants/{tenant_id}/archive", headers=admin).status_code, 409)

    def test_email_has_link_and_calendar_alarm(self):
        requests = []
        class SuccessfulSend:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *_): return False
        def capture(request, timeout):
            requests.append(json.loads(request.data))
            return SuccessfulSend()
        calendar = self.main.calendar_file("rent", 9, 4, "Rent due", datetime.now().date(), "A long event")
        event = base64.b64decode(calendar["content"]).decode()
        self.assertIn("TRIGGER:-P1D", event)
        with patch.object(self.main.urllib.request, "urlopen", side_effect=capture):
            self.assertTrue(type(self).original_send_email(["tenant@example.com"], "Please review", "Hello", calendar))
        self.assertIn("Open your tenant website: ", requests[0]["text"])
        self.assertEqual(requests[0]["attachments"][0]["filename"], "rent-9.ics")

    def test_completed_activities_are_compact_and_votes_close(self):
        main=self.main
        today=datetime.now(ZoneInfo("Australia/Perth")).date()
        with main.SessionLocal() as db:
            admin=db.query(main.User).filter_by(email="admin@example.com").one()
            voter=main.User(email="past-voter@example.com",full_name="Past Voter",password_hash="unused",role="tenant")
            nonvoter=main.User(email="past-nonvoter@example.com",full_name="Past Nonvoter",password_hash="unused",role="tenant")
            db.add_all([voter,nonvoter]);db.flush()
            past=main.Activity(title="Past outing",description="Private activity details",activity_date=today-timedelta(days=1),created_by=admin.id)
            future=main.Activity(title="Future outing",description="Upcoming details",activity_date=today+timedelta(days=3),created_by=admin.id)
            db.add_all([past,future]);db.flush()
            poll=main.Poll(activity_id=past.id,question="Attend?");db.add(poll);db.flush()
            yes=main.PollOption(poll_id=poll.id,label="Yes");db.add(yes);db.flush()
            db.add(main.Vote(poll_id=poll.id,option_id=yes.id,user_id=voter.id))
            db.commit()
            past_id,future_id,poll_id,option_id=past.id,future.id,poll.id,yes.id
            voter_token=main.token_for(voter);nonvoter_token=main.token_for(nonvoter);admin_token=main.token_for(admin)
        def activities(token):
            return self.client.get("/api/activities",headers={"Authorization":"Bearer "+token}).json()
        tenant_past=next(a for a in activities(voter_token) if a["id"]==past_id)
        self.assertEqual(tenant_past["my_vote"]["choice"],"Yes")
        self.assertIn("submitted_on",tenant_past["my_vote"])
        self.assertNotIn("description",tenant_past)
        self.assertIsNone(tenant_past["poll"])
        self.assertNotIn(past_id,[a["id"] for a in activities(nonvoter_token)])
        self.assertEqual(next(a for a in activities(nonvoter_token) if a["id"]==future_id)["description"],"Upcoming details")
        admin_past=next(a for a in activities(admin_token) if a["id"]==past_id)
        self.assertNotIn("description",admin_past)
        self.assertEqual(admin_past["poll"]["summary"],[{"label":"Yes","votes":1}])
        self.assertEqual(admin_past["poll"]["total_votes"],1)
        self.assertEqual(self.client.post(f"/api/polls/{poll_id}/vote",headers={"Authorization":"Bearer "+nonvoter_token},json={"option_id":option_id}).status_code,409)

    def test_roles_photos_and_retention(self):
        from decimal import Decimal
        from datetime import timezone
        main=self.main
        login=self.client.post("/api/auth/login",data={"username":"admin@example.com","password":"a-test-password"})
        admin={"Authorization":"Bearer "+login.json()["access_token"]}

        def create(role,email,rent):
            created=self.client.post("/api/admin/tenants",headers=admin,json={"full_name":email,
                "email":email,"move_in_date":"2025-01-01","weekly_rent":rent,"account_role":role})
            self.assertEqual(created.status_code,200,created.text)
            code=re.search(r"\b\d{6}\b",next(msg[2] for msg in reversed(self.emails)
                if msg[1]=="Your registration code" and email in msg[0])).group()
            registration=self.client.post("/api/auth/register",json={"full_name":email,
                "email":email,"password":"a-secure-test-password","invite_code":code})
            self.assertEqual(registration.status_code,200,registration.text)
            return created.json()["id"],{"Authorization":"Bearer "+registration.json()["access_token"]}

        admin_id,admin_only=create("admin","second-admin@example.com",0)
        dual_id,dual=create("tenant_admin","dual@example.com",150)
        self.assertEqual(self.client.get("/api/admin/tenants",headers=admin_only).status_code,200)
        self.assertEqual(self.client.get("/api/me",headers=admin_only).json().get("tenant"),None)
        self.assertEqual(self.client.post("/api/payments",headers=admin_only,data={"amount":"1",
            "payment_date":"2025-01-01","bank_reference":"FORBIDDEN"}).status_code,403)
        self.assertEqual(self.client.get("/api/me",headers=dual).json()["tenant"]["id"],dual_id)
        self.assertEqual(self.client.get("/api/admin/tenants",headers=dual).status_code,200)
        self.assertEqual(self.client.post("/api/admin/charges",headers=admin,json={"tenant_id":admin_id,
            "due_date":"2025-01-01","amount":1}).status_code,403)
        charge=self.client.post("/api/admin/charges",headers=admin,json={"tenant_id":dual_id,
            "due_date":"2025-01-01","amount":30}).json()["id"]
        claim=self.client.post("/api/payments",headers=dual,data={"amount":"23.00",
            "payment_date":"2025-01-01","bank_reference":"DUAL-1"})
        self.assertEqual(claim.status_code,200,claim.text)
        self.assertEqual(self.client.post(f"/api/admin/payments/{claim.json()['id']}/review",headers=dual,
            json={"decision":"approved"}).status_code,403)
        self.assertEqual(self.client.post(f"/api/admin/payments/{claim.json()['id']}/review",headers=admin,
            json={"decision":"approved"}).status_code,200)
        self.assertEqual(self.client.patch(f"/api/admin/charges/{charge}",headers=admin,
            json={"amount_paid":30,"payment_date":"2025-01-02"}).status_code,200)
        tiny_png=b"\x89PNG\r\n\x1a\n"+b"photo-data"
        self.assertEqual(self.client.post(f"/api/admin/tenants/{dual_id}/photo",headers=admin,
            files={"photo":("face.png",tiny_png,"image/png")}).status_code,200)
        self.assertEqual(self.client.get(f"/api/tenants/{dual_id}/photo",headers=dual).content,tiny_png)
        other_id,other=create("tenant","other@example.com",100)
        self.assertEqual(self.client.get(f"/api/tenants/{dual_id}/photo",headers=other).status_code,404)
        self.assertEqual(self.client.get(f"/api/tenants/{dual_id}/photo").status_code,401)

        old=datetime.now(timezone.utc)-timedelta(days=367)
        with main.SessionLocal() as db:
            payment=db.get(main.PaymentSubmission,claim.json()["id"])
            payment.submitted_at=old
            payment.receipt=tiny_png
            payment.receipt_type="image/png"
            for manual in db.scalars(main.select(main.ManualPayment).where(main.ManualPayment.tenant_id==dual_id)):
                manual.created_at=old
            db.commit()
        before=self.client.get("/api/admin/collections?year=2025",headers=admin).json()
        amount=lambda result:next(x["collected"] for x in result["tenants"] if x["tenant_id"]==dual_id)
        self.assertEqual(amount(before),30)
        self.assertEqual(self.client.post("/api/internal/prune-payments").status_code,403)
        secret={"Authorization":"Bearer test-reminder-placeholder"}
        pruned=self.client.post("/api/internal/prune-payments",headers=secret)
        self.assertEqual(pruned.status_code,200,pruned.text)
        self.assertEqual(pruned.json()["deleted_submissions"],1)
        self.assertEqual(pruned.json()["deleted_manual_payments"],1)
        self.assertEqual(self.client.post("/api/internal/prune-payments",headers=secret).json()["deleted_submissions"],0)
        self.assertEqual(amount(self.client.get("/api/admin/collections?year=2025",headers=admin).json()),30)
        self.assertEqual(self.client.get("/api/me",headers=dual).json()["tenant"]["balance"],0)
        self.assertEqual(self.client.get("/api/payments",headers=dual).json(),[])

    def test_unregistered_email_correction_replaces_code(self):
        login=self.client.post("/api/auth/login",data={"username":"admin@example.com","password":"a-test-password"})
        admin={"Authorization":"Bearer "+login.json()["access_token"]}
        with patch.object(self.main.secrets,"randbelow",return_value=123456):
            created=self.client.post("/api/admin/tenants",headers=admin,json={"full_name":"Email Correction",
                "email":"mistyped@example.com","move_in_date":"2025-01-01","weekly_rent":200})
        self.assertEqual(created.status_code,200,created.text)
        tenant_id=created.json()["id"]
        old_mail=next(m for m in reversed(self.emails) if m[1]=="Your registration code" and m[0]==["mistyped@example.com"])
        old_code=re.search(r"\b\d{6}\b",old_mail[2]).group()
        endpoint=f"/api/admin/tenants/{tenant_id}/login-email"
        duplicate=self.client.patch(endpoint,headers=admin,json={"email":"existing@example.com"})
        self.assertEqual(duplicate.status_code,409)
        with patch.object(self.main.secrets,"randbelow",return_value=234567):
            updated=self.client.patch(endpoint,headers=admin,json={"email":"corrected@example.com"})
        self.assertEqual(updated.status_code,200,updated.text)
        self.assertEqual(updated.json()["email"],"corrected@example.com")
        new_mail=next(m for m in reversed(self.emails) if m[1]=="Your registration code" and m[0]==["corrected@example.com"])
        new_code=re.search(r"\b\d{6}\b",new_mail[2]).group()
        registration={"full_name":"Email Correction","email":"corrected@example.com","password":"a-secure-test-password"}
        self.assertEqual(self.client.post("/api/auth/register",json={**registration,"invite_code":old_code}).status_code,403)
        success=self.client.post("/api/auth/register",json={**registration,"invite_code":new_code})
        self.assertEqual(success.status_code,200,success.text)
        self.assertEqual(self.client.patch(endpoint,headers=admin,json={"email":"changed-again@example.com"}).status_code,409)

    def test_unique_login_password_reset_and_summary_pdf(self):
        admin_login=self.client.post("/api/auth/login",data={"username":"admin@example.com","password":"a-test-password"})
        admin={"Authorization":"Bearer "+admin_login.json()["access_token"]}
        created=self.client.post("/api/admin/tenants",headers=admin,json={"full_name":"Seva Tenant",
            "email":"seva@example.com","unique_number":"APC-SEVA-1","allocated_seva":"Kitchen",
            "move_in_date":"2025-01-01","weekly_rent":210})
        self.assertEqual(created.status_code,200,created.text)
        code=re.search(r"\b\d{6}\b",next(m[2] for m in reversed(self.emails)
            if m[1]=="Your registration code" and m[0]==["seva@example.com"])).group()
        registered=self.client.post("/api/auth/register",json={"full_name":"Seva Tenant","email":"seva@example.com",
            "password":"first-password-123","invite_code":code})
        self.assertEqual(registered.status_code,200,registered.text)
        self.assertEqual(self.client.post("/api/auth/login",data={"username":"apc-seva-1","password":"first-password-123"}).status_code,200)
        with patch.object(self.main.secrets,"randbelow",return_value=654321):
            requested=self.client.post("/api/auth/forgot-password",json={"identifier":"APC-SEVA-1"})
        self.assertEqual(requested.status_code,200,requested.text)
        reset=self.client.post("/api/auth/reset-password",json={"identifier":"seva@example.com","code":"654321","new_password":"second-password-456"})
        self.assertEqual(reset.status_code,200,reset.text)
        self.assertEqual(self.client.post("/api/auth/login",data={"username":"APC-SEVA-1","password":"second-password-456"}).status_code,200)
        summary=self.client.get(f"/api/admin/summary.pdf?year={datetime.now().year}",headers=admin)
        self.assertEqual(summary.status_code,200,summary.text)
        self.assertTrue(summary.content.startswith(b"%PDF"))
        self.assertIn("attachment;",summary.headers["content-disposition"])


if __name__ == "__main__":
    unittest.main()
