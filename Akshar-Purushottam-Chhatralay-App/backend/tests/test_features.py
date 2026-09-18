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
        polls = self.client.get("/api/activities", headers=admin).json()
        self.assertTrue(all(row["choice"] is None for row in polls[0]["poll"]["participation"]))
        poll_id = polls[0]["poll"]["id"]
        choice_id = polls[0]["poll"]["options"][0]["id"]
        self.assertEqual(self.client.post(f"/api/polls/{poll_id}/vote", headers=tenant,
            json={"option_id": choice_id}).status_code, 200)
        votes = self.client.get("/api/activities", headers=admin).json()[0]["poll"]["participation"]
        self.assertEqual(next(row for row in votes if row["tenant_id"] == tenant_id)["choice"], "Yes")
        self.assertNotIn("participation", self.client.get("/api/activities", headers=tenant).json()[0]["poll"])

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


if __name__ == "__main__":
    unittest.main()
