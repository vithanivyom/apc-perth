import os
import logging
import json
import urllib.request
import hashlib
import secrets
import base64
import csv
import io
from zoneinfo import ZoneInfo
from decimal import Decimal
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI, Form, HTTPException, UploadFile, File, Header, status
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, LargeBinary, Numeric, String, Text, UniqueConstraint, create_engine, func, select, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://haven:haven@db:5432/haven")
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-before-production")
ALGORITHM = "HS256"
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com").lower()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "ChangeMe123!")
FRONTEND_URL = os.getenv("PUBLIC_FRONTEND_URL", "").strip().rstrip("/") or os.getenv("FRONTEND_URLS", "http://localhost:5173").split(",")[0].strip().rstrip("/")
PERTH = ZoneInfo("Australia/Perth")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

class Base(DeclarativeBase): pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(150))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="tenant", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), unique=True, nullable=True)
    full_name: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(40), default="")
    current_address: Mapped[str] = mapped_column(Text, default="")
    room: Mapped[str] = mapped_column(String(80))
    move_in_date: Mapped[date] = mapped_column(Date)
    weekly_rent: Mapped[float] = mapped_column(Numeric(10,2))
    bond_amount: Mapped[float] = mapped_column(Numeric(10,2), default=0)
    reference_name: Mapped[str] = mapped_column(String(150), default="")
    reference_phone: Mapped[str] = mapped_column(String(40), default="")
    reference_email: Mapped[str] = mapped_column(String(255), default="")
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    parent_phone: Mapped[str] = mapped_column(String(40), default="")
    university_name: Mapped[str] = mapped_column(String(150), default="")
    course_name: Mapped[str] = mapped_column(String(150), default="")
    graduation_month: Mapped[str] = mapped_column(String(7), default="")
    referee_location: Mapped[str] = mapped_column(String(150), default="")
    account_role: Mapped[str] = mapped_column(String(20), default="tenant")
    photo: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True, deferred=True)
    photo_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class RentCharge(Base):
    __tablename__ = "rent_charges"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    due_date: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[float] = mapped_column(Numeric(10,2))
    amount_paid: Mapped[float] = mapped_column(Numeric(10,2), default=0)
    note: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class ManualPayment(Base):
    __tablename__ = "manual_payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    charge_id: Mapped[int] = mapped_column(ForeignKey("rent_charges.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(10,2))
    payment_date: Mapped[date] = mapped_column(Date, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class ArchivedCollection(Base):
    __tablename__ = "archived_collections"
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12,2), default=0)

class BulkRentRun(Base):
    __tablename__ = "bulk_rent_runs"
    due_date: Mapped[date] = mapped_column(Date, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Activity(Base):
    __tablename__ = "activities"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text, default="")
    activity_date: Mapped[date] = mapped_column(Date, index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Poll(Base):
    __tablename__ = "polls"
    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id"), index=True)
    question: Mapped[str] = mapped_column(String(300))
    closes_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class PollOption(Base):
    __tablename__ = "poll_options"
    id: Mapped[int] = mapped_column(primary_key=True)
    poll_id: Mapped[int] = mapped_column(ForeignKey("polls.id"), index=True)
    label: Mapped[str] = mapped_column(String(150))

class Vote(Base):
    __tablename__ = "votes"
    __table_args__ = (UniqueConstraint("poll_id", "user_id", name="uq_poll_user_vote"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    poll_id: Mapped[int] = mapped_column(ForeignKey("polls.id"), index=True)
    option_id: Mapped[int] = mapped_column(ForeignKey("poll_options.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class PaymentSubmission(Base):
    __tablename__ = "payment_submissions"
    __table_args__ = (UniqueConstraint("tenant_id", "bank_reference", name="uq_tenant_bank_reference"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    submitted_name: Mapped[str] = mapped_column(String(150))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    payment_date: Mapped[date] = mapped_column(Date)
    bank_reference: Mapped[str] = mapped_column(String(120))
    bank_details: Mapped[str] = mapped_column(String(300), default="")
    receipt: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    receipt_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    state: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    review_note: Mapped[str] = mapped_column(String(300), default="")

class NotificationRecipient(Base):
    __tablename__ = "notification_recipients"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)

class RegistrationInvite(Base):
    __tablename__ = "registration_invites"
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

class ReminderDelivery(Base):
    __tablename__ = "reminder_deliveries"
    __table_args__ = (UniqueConstraint("kind", "item_id", "tenant_id", name="uq_reminder_item_tenant"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))
    item_id: Mapped[int] = mapped_column(Integer)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

def calendar_file(kind:str, item_id:int, tenant_id:int, title:str, when:date, details:str="") -> dict:
    def safe(value):
        return str(value).replace("\\", "\\\\").replace("\r", "").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")
    lines=["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//APC//Chhatralay Calendar//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "BEGIN:VEVENT",
        f"UID:{kind}-{item_id}-{tenant_id}@apcperth.site",f"DTSTAMP:{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}",
        f"DTSTART;VALUE=DATE:{when:%Y%m%d}",f"DTEND;VALUE=DATE:{when+timedelta(days=1):%Y%m%d}",
        f"SUMMARY:{safe(title)}",f"DESCRIPTION:{safe(details + ' Open: ' + FRONTEND_URL)}", f"URL:{FRONTEND_URL}",
        "BEGIN:VALARM", "TRIGGER:-P1D", "ACTION:DISPLAY", "DESCRIPTION:Reminder", "END:VALARM", "END:VEVENT", "END:VCALENDAR", ""]
    # Fold long UTF-8 lines as required by iCalendar (75 octets per line).
    folded=[]
    for line in lines:
        part=""
        for char in line:
            if len((part+char).encode("utf-8"))>70:
                folded.append(part)
                part=" "+char
            else: part+=char
        folded.append(part)
    event="\r\n".join(folded)
    return {"filename":f"{kind}-{item_id}.ics", "content":base64.b64encode(event.encode()).decode()}

def invite_tenant(db:Session,tasks:BackgroundTasks,tenant:Tenant):
    if not os.getenv("RESEND_API_KEY") or not os.getenv("EMAIL_FROM"):
        raise HTTPException(503,"Email is not configured. Set RESEND_API_KEY and EMAIL_FROM first.")
    if tenant.user_id: raise HTTPException(409,"Tenant account already registered")
    code=f"{secrets.randbelow(1000000):06d}"
    row=db.scalar(select(RegistrationInvite).where(RegistrationInvite.tenant_id==tenant.id).with_for_update())
    now=datetime.now(timezone.utc)
    last=row.last_sent_at if row else None
    if last and (last.replace(tzinfo=timezone.utc) if last.tzinfo is None else last)>now-timedelta(minutes=1):
        raise HTTPException(429,"Wait one minute before sending another code")
    if row is None:
        row=RegistrationInvite(tenant_id=tenant.id,token_hash="",expires_at=datetime.now(timezone.utc))
        db.add(row)
    row.token_hash=hashlib.sha256(code.encode()).hexdigest()
    row.expires_at=now+timedelta(minutes=15)
    row.last_sent_at=now
    row.failed_attempts=0
    db.commit()
    tasks.add_task(send_email,[tenant.email],"Your registration code",f"Your six-digit code is {code}. It expires in 15 minutes.")

def send_email(recipients: list[str], subject: str, body: str, attachment: Optional[dict]=None):
    key = os.getenv("RESEND_API_KEY", "")
    sender = os.getenv("EMAIL_FROM", "")
    if not key or not sender:
        logging.warning("Email not configured: set RESEND_API_KEY and EMAIL_FROM")
        return False
    success=True
    for recipient in set(x.lower() for x in recipients if x):
        try:
            payload={"from":sender,"to":[recipient],"subject":subject,"text":body.rstrip()+"\n\nOpen your tenant website: "+FRONTEND_URL}
            if attachment: payload["attachments"]=[attachment]
            request=urllib.request.Request("https://api.resend.com/emails",
                data=json.dumps(payload).encode(),
                headers={"Authorization":"Bearer "+key,"Content-Type":"application/json","User-Agent":"apc-perth/1.0"},method="POST")
            with urllib.request.urlopen(request, timeout=15) as response:
                if response.status>=300: raise RuntimeError("Email provider rejected request")
        except Exception:
            success=False
            logging.exception("Notification delivery failed for %s", recipient)
    return success

def notify(db: Session, tasks: BackgroundTasks, recipients: list[str], subject: str, body: str):
    extra = db.scalars(select(NotificationRecipient)).all()
    admins=db.scalars(select(User).where(User.role.in_(("admin","tenant_admin")),User.is_active==True)).all()
    tasks.add_task(send_email, recipients + [a.email for a in admins] + [r.email for r in extra], subject, body)

def notify_calendar(db:Session,tasks:BackgroundTasks,tenant:Tenant,kind:str,item_id:int,title:str,when:date,body:str,staff_copy:bool=True):
    tasks.add_task(send_email,[tenant.email],title,body,calendar_file(kind,item_id,tenant.id,title,when,body))
    if staff_copy:
        tasks.add_task(send_email,[a.email for a in db.scalars(select(User).where(User.role.in_(("admin","tenant_admin")),User.is_active==True))] +
            [r.email for r in db.scalars(select(NotificationRecipient))],title,f"{tenant.full_name}: {body}")

def payment_json(p: PaymentSubmission, tenant: Tenant):
    return {"id": p.id, "tenant_id": tenant.id, "tenant_name": tenant.full_name,
            "tenant_email": tenant.email, "submitted_name": p.submitted_name,
            "amount": float(p.amount), "payment_date": p.payment_date,
            "bank_reference": p.bank_reference, "bank_details": p.bank_details,
            "has_receipt": bool(p.receipt), "state": p.state,
            "submitted_at": p.submitted_at, "reviewed_at": p.reviewed_at,
            "review_note": p.review_note}

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
app = FastAPI(title="Akshar Purushottam Chhatralay API")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("FRONTEND_URLS","http://localhost:5173").split(","), allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

def db_session():
    db = SessionLocal()
    try: yield db
    finally: db.close()

def token_for(user: User):
    return jwt.encode({"sub": str(user.id), "role": user.role, "exp": datetime.now(timezone.utc)+timedelta(minutes=15)}, SECRET_KEY, algorithm=ALGORITHM)

def current_user(token: str=Depends(oauth2), db: Session=Depends(db_session)):
    try: user_id = int(jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])["sub"])
    except (JWTError, KeyError, ValueError): raise HTTPException(401, "Invalid or expired login")
    user = db.get(User, user_id)
    if not user or not user.is_active: raise HTTPException(401, "Account unavailable")
    return user

def admin(user: User=Depends(current_user)):
    if user.role not in ("admin","tenant_admin"): raise HTTPException(403, "Admin access required")
    return user

class RegisterIn(BaseModel):
    full_name: str
    email: EmailStr
    password: str = Field(min_length=8)
    invite_code: str
class TenantIn(BaseModel):
    full_name: str; email: EmailStr; phone: str=""; current_address: str=""; room: str=""
    move_in_date: date; weekly_rent: float=Field(ge=0); bond_amount: float=0
    account_role: str = Field(default="tenant", pattern=r"^(tenant|admin|tenant_admin)$")
    reference_name: str=""; reference_phone: str=""; reference_email: str=""
    date_of_birth: Optional[date]=None; parent_phone: str=""; university_name: str=""; course_name: str=""
    graduation_month: str=Field(default="", pattern=r"^$|^\d{4}-(0[1-9]|1[0-2])$")
    referee_location: str=""
class TenantProfileUpdate(BaseModel):
    full_name: str = Field(min_length=1,max_length=150)
    phone: str = Field(default="",max_length=40)
    date_of_birth: Optional[date] = None
    parent_phone: str = Field(default="",max_length=40)
    current_address: str = ""
    move_in_date: date
    university_name: str = Field(default="",max_length=150)
    course_name: str = Field(default="",max_length=150)
    graduation_month: str = Field(default="",pattern=r"^$|^\d{4}-(0[1-9]|1[0-2])$")
    reference_name: str = Field(default="",max_length=150)
    reference_phone: str = Field(default="",max_length=40)
    referee_location: str = Field(default="",max_length=150)
class ChargeIn(BaseModel):
    tenant_id: int; due_date: date; amount: float=Field(gt=0); note: str=""
class BulkChargeIn(BaseModel):
    due_date: date
class PaymentIn(BaseModel):
    amount_paid: float=Field(ge=0)
    payment_date: Optional[date]=None
class ActivityIn(BaseModel):
    title: str; description: str=""; activity_date: date; poll_question: Optional[str]=None; options: list[str]=[]
class VoteIn(BaseModel):
    option_id: int
class ReviewIn(BaseModel):
    decision: str
    note: str = Field(default="", max_length=300)
class RecipientIn(BaseModel):
    email: EmailStr
class PersonalEmailIn(BaseModel):
    subject: str = Field(min_length=1,max_length=180)
    message: str = Field(min_length=1,max_length=3000)
class PasswordChangeIn(BaseModel):
    old_password: str
    new_password: str = Field(min_length=12)

@app.on_event("startup")
def startup():
    Base.metadata.create_all(engine)
    # Existing installations need these new nullable/defaulted columns before ORM reads.
    existing={c["name"] for c in inspect(engine).get_columns("tenants")}
    fields={"date_of_birth":"DATE", "parent_phone":"VARCHAR(40) DEFAULT '' NOT NULL",
        "university_name":"VARCHAR(150) DEFAULT '' NOT NULL", "course_name":"VARCHAR(150) DEFAULT '' NOT NULL",
        "graduation_month":"VARCHAR(7) DEFAULT '' NOT NULL", "referee_location":"VARCHAR(150) DEFAULT '' NOT NULL",
        "account_role":"VARCHAR(20) DEFAULT 'tenant' NOT NULL", "photo":"BYTEA", "photo_type":"VARCHAR(30)"}
    with engine.begin() as connection:
        for name,definition in fields.items():
            if name not in existing: connection.execute(text(f"ALTER TABLE tenants ADD COLUMN {name} {definition}"))
        invite_columns={c["name"] for c in inspect(connection).get_columns("registration_invites")}
        if "failed_attempts" not in invite_columns: connection.execute(text("ALTER TABLE registration_invites ADD COLUMN failed_attempts INTEGER DEFAULT 0 NOT NULL"))
        if "last_sent_at" not in invite_columns: connection.execute(text("ALTER TABLE registration_invites ADD COLUMN last_sent_at TIMESTAMP WITH TIME ZONE"))
    with SessionLocal() as db:
        if not db.scalar(select(User).where(User.email == ADMIN_EMAIL)):
            db.add(User(email=ADMIN_EMAIL, full_name="Administrator", password_hash=pwd.hash(ADMIN_PASSWORD), role="admin"))
            db.commit()

@app.get("/api/health")
def health(): return {"status":"ok"}

@app.post("/api/auth/register")
def register(data:RegisterIn, tasks:BackgroundTasks, db:Session=Depends(db_session)):
    email=data.email.lower()
    tenant=db.scalar(select(Tenant).where(func.lower(Tenant.email)==email))
    if not tenant or not tenant.is_active: raise HTTPException(403,"Ask the administrator to add your active tenant email first")
    if tenant.user_id: raise HTTPException(409,"This tenant account is already registered")
    invite=db.scalar(select(RegistrationInvite).where(RegistrationInvite.tenant_id==tenant.id).with_for_update())
    expires=invite.expires_at if invite else None
    if expires and expires.tzinfo is None: expires=expires.replace(tzinfo=timezone.utc)
    if not invite or expires < datetime.now(timezone.utc) or invite.failed_attempts>=5:
        raise HTTPException(403,"Code expired or locked. Ask the admin to resend it.")
    if not (len(data.invite_code)==6 and data.invite_code.isascii() and data.invite_code.isdecimal() and secrets.compare_digest(invite.token_hash,hashlib.sha256(data.invite_code.encode()).hexdigest())):
        invite.failed_attempts+=1; db.commit()
        raise HTTPException(403,"Invalid code. Ask the admin to resend it after five failed attempts.")
    user=User(email=email,full_name=tenant.full_name,password_hash=pwd.hash(data.password),role=tenant.account_role)
    db.add(user); db.flush(); tenant.user_id=user.id; db.delete(invite); db.commit()
    notify(db,tasks,[tenant.email],"Tenant account created",f"{tenant.full_name} registered their tenant account.")
    return {"access_token":token_for(user),"token_type":"bearer","role":user.role}

@app.post("/api/auth/login")
def login(form:OAuth2PasswordRequestForm=Depends(), db:Session=Depends(db_session)):
    user=db.scalar(select(User).where(func.lower(User.email)==form.username.lower()))
    if not user or not user.is_active or not pwd.verify(form.password,user.password_hash): raise HTTPException(401,"Incorrect email or password or inactive account")
    return {"access_token":token_for(user),"token_type":"bearer","role":user.role,"name":user.full_name}

@app.post("/api/auth/refresh")
def refresh(user:User=Depends(current_user)):
    return {"access_token":token_for(user),"token_type":"bearer"}

@app.post("/api/me/change-password")
def change_password(data:PasswordChangeIn,user:User=Depends(current_user),db:Session=Depends(db_session)):
    if not pwd.verify(data.old_password,user.password_hash): raise HTTPException(403,"Current password is incorrect")
    user.password_hash=pwd.hash(data.new_password)
    db.commit()
    return {"ok":True}

@app.get("/api/me")
def me(user:User=Depends(current_user),db:Session=Depends(db_session)):
    base={"id":user.id,"name":user.full_name,"email":user.email,"role":user.role}
    if user.role in ("tenant","tenant_admin"):
        tenant=db.scalar(select(Tenant).where(Tenant.user_id==user.id))
        if tenant:
            charges=db.scalars(select(RentCharge).where(RentCharge.tenant_id==tenant.id).order_by(RentCharge.due_date.desc())).all()
            base["tenant"]={"id":tenant.id,"room":tenant.room,"weekly_rent":float(tenant.weekly_rent),"balance":sum(float(c.amount)-float(c.amount_paid) for c in charges),"charges":[{"id":c.id,"due_date":c.due_date,"amount":float(c.amount),"paid":float(c.amount_paid),"balance":float(c.amount)-float(c.amount_paid)} for c in charges]}
    return base

@app.get("/api/admin/dashboard")
def dashboard(_:User=Depends(admin),db:Session=Depends(db_session)):
    tenants=db.scalars(select(Tenant).where(Tenant.is_active==True,Tenant.account_role!="admin").order_by(Tenant.full_name)).all()
    rows=[]
    for t in tenants:
        charges=db.scalars(select(RentCharge).where(RentCharge.tenant_id==t.id)).all()
        balance=sum(float(c.amount)-float(c.amount_paid) for c in charges)
        rows.append({"id":t.id,"name":t.full_name,"email":t.email,"room":t.room,"registered":bool(t.user_id),"weekly_rent":float(t.weekly_rent),"balance":balance})
    return {"tenants":rows,"pending":[r for r in rows if r["balance"]>0],"total_outstanding":sum(r["balance"] for r in rows)}

def tenant_profile(tenant:Tenant, db:Session):
    charges=db.scalars(select(RentCharge).where(RentCharge.tenant_id==tenant.id).order_by(RentCharge.due_date.desc(),RentCharge.id.desc())).all()
    payments=db.scalars(select(PaymentSubmission).where(PaymentSubmission.tenant_id==tenant.id).order_by(PaymentSubmission.id.desc())).all()
    return {"id":tenant.id,"full_name":tenant.full_name,"email":tenant.email,"phone":tenant.phone,
            "current_address":tenant.current_address,"room":tenant.room,"move_in_date":tenant.move_in_date,
            "date_of_birth":tenant.date_of_birth,"parent_phone":tenant.parent_phone,
            "university_name":tenant.university_name,"course_name":tenant.course_name,
            "graduation_month":tenant.graduation_month,"referee_location":tenant.referee_location,
            "weekly_rent":float(tenant.weekly_rent),"bond_amount":float(tenant.bond_amount),
            "reference_name":tenant.reference_name,"reference_phone":tenant.reference_phone,
            "reference_email":tenant.reference_email,"is_active":tenant.is_active,"registered":bool(tenant.user_id),
            "account_role":tenant.account_role,"has_photo":bool(tenant.photo),
            "charges":[{"id":c.id,"due_date":c.due_date,"amount":float(c.amount),"paid":float(c.amount_paid),"note":c.note} for c in charges],
            "payments":[payment_json(p,tenant) for p in payments]}

@app.get("/api/admin/collections")
def collections(year:int, _:User=Depends(admin),db:Session=Depends(db_session)):
    if year<2000 or year>2100: raise HTTPException(400,"Choose a year between 2000 and 2100")
    start,end=date(year,1,1),date(year+1,1,1)
    tenants=db.scalars(select(Tenant).order_by(Tenant.full_name,Tenant.id)).all()
    amounts={t.id:Decimal("0.00") for t in tenants}
    for p in db.scalars(select(PaymentSubmission).where(PaymentSubmission.state=="approved",PaymentSubmission.payment_date>=start,PaymentSubmission.payment_date<end)):
        amounts[p.tenant_id]+=p.amount
    for p in db.scalars(select(ManualPayment).where(ManualPayment.payment_date>=start,ManualPayment.payment_date<end)):
        amounts[p.tenant_id]+=p.amount
    for archived in db.scalars(select(ArchivedCollection).where(ArchivedCollection.year==year)):
        amounts[archived.tenant_id]+=archived.amount
    approved=db.execute(select(PaymentSubmission.tenant_id,func.sum(PaymentSubmission.amount)).where(PaymentSubmission.state=="approved").group_by(PaymentSubmission.tenant_id)).all()
    manually_recorded=db.execute(select(ManualPayment.tenant_id,func.sum(ManualPayment.amount)).group_by(ManualPayment.tenant_id)).all()
    from_submissions=dict(approved)
    from_manual=dict(manually_recorded)
    archived_totals=dict(db.execute(select(ArchivedCollection.tenant_id,func.sum(ArchivedCollection.amount)).group_by(ArchivedCollection.tenant_id)).all())
    rows=[]
    for t in tenants:
        total_paid=db.scalar(select(func.sum(RentCharge.amount_paid)).where(RentCharge.tenant_id==t.id)) or Decimal("0.00")
        historical=max(Decimal("0.00"),total_paid-(from_submissions.get(t.id) or 0)-(from_manual.get(t.id) or 0)-(archived_totals.get(t.id) or 0))
        rows.append({"tenant_id":t.id,"name":t.full_name,"room":t.room,"active":t.is_active,
                     "collected":float(amounts[t.id]),"historical_undated":float(historical)})
    return {"year":year,"start":start,"end_exclusive":end,"total":float(sum(amounts.values())),
            "historical_undated":float(sum(Decimal(str(r["historical_undated"])) for r in rows)),"tenants":rows}

@app.get("/api/admin/tenants")
def list_tenants(_:User=Depends(admin),db:Session=Depends(db_session)):
    tenants=db.scalars(select(Tenant).order_by(Tenant.full_name,Tenant.id)).all()
    return [{"id":t.id,"name":t.full_name,"email":t.email,"room":t.room,
             "is_active":t.is_active,"registered":bool(t.user_id),"account_role":t.account_role} for t in tenants]

@app.get("/api/admin/tenants/report.csv")
def tenant_csv(_:User=Depends(admin),db:Session=Depends(db_session)):
    """One row per tenant, including archived tenants and financial totals."""
    rows=db.scalars(select(Tenant).order_by(Tenant.full_name,Tenant.id)).all()
    output=io.StringIO()
    columns=["Tenant number","Status","Registered","Role","Name","Email","Mobile number","Date of birth",
        "Parent mobile","Home address","Arrival date","University","Course","Graduation month",
        "Referee name","Referee contact","Referee location","Room","Weekly rent AUD",
        "Bond AUD","Total charged AUD","Total paid AUD","Outstanding AUD"]
    writer=csv.writer(output); writer.writerow(columns)
    def cell(value):
        s="" if value is None else str(value)
        return "'"+s if s.lstrip().startswith(("=","+","-","@","\t","\r","\n")) else s
    for t in rows:
        charges=db.scalars(select(RentCharge).where(RentCharge.tenant_id==t.id)).all()
        total=sum((c.amount for c in charges),Decimal("0.00"))
        paid=sum((c.amount_paid for c in charges),Decimal("0.00"))
        writer.writerow([cell(x) for x in (t.id,"Active" if t.is_active else "Archived",bool(t.user_id),t.account_role,
            t.full_name,t.email,t.phone,t.date_of_birth,t.parent_phone,t.current_address,t.move_in_date,
            t.university_name,t.course_name,t.graduation_month,t.reference_name,t.reference_phone,
            t.referee_location,t.room,t.weekly_rent,t.bond_amount,total,paid,total-paid)])
    return Response(content="\ufeff"+output.getvalue(),media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition":"attachment; filename=apc-tenants-all.csv","Cache-Control":"private, no-store"})

@app.get("/api/admin/tenants/{tenant_id}")
def tenant_details(tenant_id:int,_:User=Depends(admin),db:Session=Depends(db_session)):
    tenant=db.get(Tenant,tenant_id)
    if not tenant: raise HTTPException(404,"Tenant not found")
    return tenant_profile(tenant,db)

@app.get("/api/tenants/{tenant_id}/photo")
def tenant_photo(tenant_id:int,user:User=Depends(current_user),db:Session=Depends(db_session)):
    tenant=db.get(Tenant,tenant_id)
    if not tenant or (user.role not in ("admin","tenant_admin") and tenant.user_id!=user.id):
        raise HTTPException(404,"Photo not found")
    if not tenant.photo: raise HTTPException(404,"Photo not found")
    return Response(tenant.photo,media_type=tenant.photo_type,
        headers={"Cache-Control":"private, no-store","X-Content-Type-Options":"nosniff"})

@app.post("/api/admin/tenants/{tenant_id}/photo")
async def upload_tenant_photo(tenant_id:int,photo:UploadFile=File(...),_:User=Depends(admin),db:Session=Depends(db_session)):
    tenant=db.get(Tenant,tenant_id)
    if not tenant: raise HTTPException(404,"Tenant not found")
    content=await photo.read(1024*1024+1)
    if len(content)>1024*1024: raise HTTPException(413,"Photo must be smaller than 1 MB")
    if content.startswith(b"\xff\xd8\xff"): media="image/jpeg"
    elif content.startswith(b"\x89PNG\r\n\x1a\n"): media="image/png"
    elif content[:4]==b"RIFF" and content[8:12]==b"WEBP": media="image/webp"
    else: raise HTTPException(415,"Choose a JPG, PNG or WebP photo")
    tenant.photo=content;tenant.photo_type=media;db.commit()
    return {"ok":True}

@app.delete("/api/admin/tenants/{tenant_id}/photo")
def remove_tenant_photo(tenant_id:int,_:User=Depends(admin),db:Session=Depends(db_session)):
    tenant=db.get(Tenant,tenant_id)
    if not tenant: raise HTTPException(404,"Tenant not found")
    tenant.photo=None;tenant.photo_type=None;db.commit()
    return {"ok":True}

@app.patch("/api/admin/tenants/{tenant_id}")
def edit_tenant(tenant_id:int,data:TenantProfileUpdate,_:User=Depends(admin),db:Session=Depends(db_session)):
    tenant=db.get(Tenant,tenant_id)
    if not tenant: raise HTTPException(404,"Tenant not found")
    for name,value in data.model_dump().items(): setattr(tenant,name,value.strip() if isinstance(value,str) else value)
    if tenant.user_id:
        user=db.get(User,tenant.user_id)
        if user: user.full_name=tenant.full_name
    db.commit()
    return tenant_profile(tenant,db)

@app.post("/api/admin/tenants/{tenant_id}/archive")
def archive_tenant(tenant_id:int,_:User=Depends(admin),db:Session=Depends(db_session)):
    tenant=db.scalar(select(Tenant).where(Tenant.id==tenant_id).with_for_update())
    if not tenant: raise HTTPException(404,"Tenant not found")
    if not tenant.is_active: raise HTTPException(409,"Tenant already archived")
    charges=db.scalars(select(RentCharge).where(RentCharge.tenant_id==tenant_id).with_for_update()).all()
    outstanding=sum((max(Decimal("0.00"),c.amount-c.amount_paid) for c in charges),Decimal("0.00"))
    if outstanding>0: raise HTTPException(409,f"Cannot remove tenant: AUD {outstanding:.2f} rent is still outstanding")
    if db.scalar(select(PaymentSubmission.id).where(PaymentSubmission.tenant_id==tenant_id,PaymentSubmission.state=="pending")):
        raise HTTPException(409,"Review the tenant's pending payment submissions before removing them")
    tenant.is_active=False
    if tenant.user_id:
        user=db.get(User,tenant.user_id)
        if user: user.is_active=False
    db.commit()
    return {"ok":True}

@app.post("/api/admin/tenants/{tenant_id}/restore")
def restore_tenant(tenant_id:int,_:User=Depends(admin),db:Session=Depends(db_session)):
    tenant=db.get(Tenant,tenant_id)
    if not tenant: raise HTTPException(404,"Tenant not found")
    if tenant.is_active: raise HTTPException(409,"Tenant is already active")
    tenant.is_active=True
    if tenant.user_id:
        user=db.get(User,tenant.user_id)
        if user: user.is_active=True
    db.commit()
    return {"ok":True}

@app.get("/api/me/profile")
def my_profile(user:User=Depends(current_user),db:Session=Depends(db_session)):
    if user.role not in ("tenant","tenant_admin"): raise HTTPException(403,"Tenant access required")
    tenant=db.scalar(select(Tenant).where(Tenant.user_id==user.id))
    if not tenant: raise HTTPException(404,"Your tenant profile is not linked")
    return tenant_profile(tenant,db)

@app.post("/api/admin/tenants")
def add_tenant(data:TenantIn,tasks:BackgroundTasks,_:User=Depends(admin),db:Session=Depends(db_session)):
    if not os.getenv("RESEND_API_KEY") or not os.getenv("EMAIL_FROM"):
        raise HTTPException(503,"Email is not configured. Set RESEND_API_KEY and EMAIL_FROM first.")
    if db.scalar(select(Tenant).where(func.lower(Tenant.email)==data.email.lower())): raise HTTPException(409,"Tenant email already exists")
    if db.scalar(select(User).where(func.lower(User.email)==data.email.lower())): raise HTTPException(409,"An account with this email already exists")
    if data.account_role!="admin" and data.weekly_rent<=0: raise HTTPException(400,"Weekly rent is required for a tenant")
    tenant=Tenant(**data.model_dump()); tenant.email=data.email.lower(); db.add(tenant); db.commit(); db.refresh(tenant)
    invite_tenant(db,tasks,tenant)
    notify(db,tasks,[],"New tenant added",f"Tenant {tenant.full_name} was added. Sign in to review details.")
    return {"id":tenant.id}

@app.post("/api/admin/tenants/{tenant_id}/invite")
def resend_invite(tenant_id:int,tasks:BackgroundTasks,_:User=Depends(admin),db:Session=Depends(db_session)):
    tenant=db.get(Tenant,tenant_id)
    if not tenant: raise HTTPException(404,"Tenant not found")
    invite_tenant(db,tasks,tenant)
    return {"ok":True}

@app.post("/api/admin/tenants/{tenant_id}/email")
def email_tenant(tenant_id:int,data:PersonalEmailIn,tasks:BackgroundTasks,_:User=Depends(admin),db:Session=Depends(db_session)):
    tenant=db.get(Tenant,tenant_id)
    if not tenant: raise HTTPException(404,"Tenant not found")
    if not os.getenv("RESEND_API_KEY") or not os.getenv("EMAIL_FROM"):
        raise HTTPException(503,"Email is not configured")
    tasks.add_task(send_email,[tenant.email],data.subject.strip(),data.message.strip())
    return {"queued":True,"recipient":tenant.email}

@app.post("/api/admin/charges")
def add_charge(data:ChargeIn,tasks:BackgroundTasks,_:User=Depends(admin),db:Session=Depends(db_session)):
    tenant=db.scalar(select(Tenant).where(Tenant.id==data.tenant_id).with_for_update())
    if not tenant: raise HTTPException(404,"Tenant not found")
    if not tenant.is_active: raise HTTPException(409,"Restore the archived tenant before adding rent")
    if tenant.account_role=="admin": raise HTTPException(403,"Admin-only profiles do not pay rent")
    charge=RentCharge(**data.model_dump()); db.add(charge); db.commit()
    notify_calendar(db,tasks,tenant,"rent",charge.id,"Rent due",data.due_date,
        f"Rent of AUD {data.amount:.2f} is due on {data.due_date}. Add the attached calendar event and sign in to view your balance.")
    return {"id":charge.id}

@app.post("/api/admin/charges/all")
def charge_all(data:BulkChargeIn,tasks:BackgroundTasks,_:User=Depends(admin),db:Session=Depends(db_session)):
    tenants=db.scalars(select(Tenant).where(Tenant.is_active==True,Tenant.account_role!="admin").order_by(Tenant.id).with_for_update()).all()
    if not tenants: raise HTTPException(400,"Add an active tenant first")
    if db.get(BulkRentRun,data.due_date): raise HTTPException(409,"Rent charges for this date were already created for all tenants")
    db.add(BulkRentRun(due_date=data.due_date))
    charges=[RentCharge(tenant_id=t.id,due_date=data.due_date,amount=t.weekly_rent,
                           note="Rent due on "+data.due_date.isoformat()) for t in tenants]
    db.add_all(charges)
    try: db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,"Rent charges for this date were already created for all tenants")
    for t,c in zip(tenants,charges):
        notify_calendar(db,tasks,t,"rent",c.id,"Rent due",data.due_date,
               f"Hi {t.full_name}, rent of AUD {t.weekly_rent:.2f} is due on {data.due_date}. Add the attached calendar event.")
    return {"created":len(tenants),"due_date":data.due_date}

@app.patch("/api/admin/charges/{charge_id}")
def record_payment(charge_id:int,data:PaymentIn,tasks:BackgroundTasks,_:User=Depends(admin),db:Session=Depends(db_session)):
    charge=db.scalar(select(RentCharge).where(RentCharge.id==charge_id).with_for_update())
    if not charge: raise HTTPException(404,"Charge not found")
    if Decimal(str(data.amount_paid))>charge.amount: raise HTTPException(400,"Amount paid exceeds charge")
    delta=Decimal(str(data.amount_paid))-charge.amount_paid
    if delta:
        db.add(ManualPayment(tenant_id=charge.tenant_id,charge_id=charge.id,amount=delta,
                             payment_date=data.payment_date or date.today()))
    charge.amount_paid=data.amount_paid; db.commit()
    tenant=db.get(Tenant,charge.tenant_id)
    notify(db,tasks,[tenant.email],"Rent payment updated",f"A rent payment was updated for {tenant.full_name}. Sign in to see the current balance.")
    return {"ok":True}

@app.get("/api/payments")
def my_payments(user:User=Depends(current_user),db:Session=Depends(db_session)):
    tenant=db.scalar(select(Tenant).where(Tenant.user_id==user.id))
    if not tenant: return []
    payments=db.scalars(select(PaymentSubmission).where(PaymentSubmission.tenant_id==tenant.id).order_by(PaymentSubmission.id.desc())).all()
    return [payment_json(p,tenant) for p in payments]

@app.post("/api/payments")
async def submit_payment(tasks:BackgroundTasks,amount:Decimal=Form(...),payment_date:date=Form(...),
                         bank_reference:str=Form(...),bank_details:str=Form(""),receipt:Optional[UploadFile]=File(None),
                         user:User=Depends(current_user),db:Session=Depends(db_session)):
    if user.role not in ("tenant","tenant_admin"): raise HTTPException(403,"Tenant access required")
    tenant=db.scalar(select(Tenant).where(Tenant.user_id==user.id,Tenant.is_active==True))
    if not tenant: raise HTTPException(403,"Tenant record unavailable")
    if amount<=0 or amount>1000000 or amount.as_tuple().exponent < -2: raise HTTPException(400,"Enter a valid amount in dollars and cents")
    reference=bank_reference.strip()
    if not reference or len(reference)>120 or len(bank_details)>300: raise HTTPException(400,"Invalid bank reference or details")
    photo=None; photo_type=None
    if receipt and receipt.filename:
        photo=await receipt.read(2*1024*1024+1)
        if len(photo)>2*1024*1024: raise HTTPException(413,"Receipt must be under 2 MB")
        if photo.startswith(b"\xff\xd8\xff"): photo_type="image/jpeg"
        elif photo.startswith(b"\x89PNG\r\n\x1a\n"): photo_type="image/png"
        elif photo[:4]==b"RIFF" and photo[8:12]==b"WEBP": photo_type="image/webp"
        else: raise HTTPException(415,"Upload a JPG, PNG, or WebP image")
    payment=PaymentSubmission(tenant_id=tenant.id,submitted_name=tenant.full_name,amount=amount,
        payment_date=payment_date,bank_reference=reference,bank_details=bank_details.strip(),receipt=photo,receipt_type=photo_type)
    db.add(payment)
    try: db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409,"This bank reference has already been submitted")
    db.refresh(payment)
    notify(db,tasks,[tenant.email],"Payment submitted",f"{tenant.full_name} submitted a payment of AUD {amount:.2f} (reference {reference}). It is pending admin review. Sign in to see its status.")
    return payment_json(payment,tenant)

@app.get("/api/admin/payments")
def admin_payments(_:User=Depends(admin),db:Session=Depends(db_session)):
    rows=db.execute(select(PaymentSubmission,Tenant).join(Tenant,PaymentSubmission.tenant_id==Tenant.id).order_by(PaymentSubmission.id.desc())).all()
    return [payment_json(p,t) for p,t in rows]

@app.get("/api/admin/payments/{payment_id}/receipt")
def admin_receipt(payment_id:int,_:User=Depends(admin),db:Session=Depends(db_session)):
    payment=db.get(PaymentSubmission,payment_id)
    if not payment or not payment.receipt: raise HTTPException(404,"Receipt not found")
    return Response(payment.receipt,media_type=payment.receipt_type,headers={"Cache-Control":"private, no-store","X-Content-Type-Options":"nosniff"})

@app.post("/api/admin/payments/{payment_id}/review")
def review_payment(payment_id:int,data:ReviewIn,tasks:BackgroundTasks,user:User=Depends(admin),db:Session=Depends(db_session)):
    if data.decision not in ("approved","rejected"): raise HTTPException(400,"Choose approved or rejected")
    payment=db.scalar(select(PaymentSubmission).where(PaymentSubmission.id==payment_id).with_for_update())
    if not payment: raise HTTPException(404,"Submission not found")
    if payment.state!="pending": raise HTTPException(409,"Payment already reviewed")
    tenant=db.get(Tenant,payment.tenant_id)
    if tenant.user_id==user.id: raise HTTPException(403,"You cannot review your own payment")
    if data.decision=="approved":
        charges=db.scalars(select(RentCharge).where(RentCharge.tenant_id==tenant.id).order_by(RentCharge.due_date,RentCharge.id).with_for_update()).all()
        remaining=payment.amount
        for charge in charges:
            outstanding=charge.amount-charge.amount_paid
            if outstanding>0:
                paid=min(outstanding,remaining)
                charge.amount_paid+=paid
                remaining-=paid
            if remaining<=0: break
        if remaining>0: raise HTTPException(409,"Payment exceeds outstanding rent. Add a charge or reject this submission.")
    payment.state=data.decision
    payment.reviewed_at=datetime.now(timezone.utc)
    payment.reviewed_by=user.id
    payment.review_note=data.note
    db.commit()
    notify(db,tasks,[tenant.email],f"Payment {data.decision}",f"Payment reference {payment.bank_reference} for AUD {payment.amount:.2f} was {data.decision}. {data.note} Sign in for the latest balance.")
    return {"ok":True}

@app.get("/api/admin/notification-recipients")
def recipients(_:User=Depends(admin),db:Session=Depends(db_session)):
    return [{"id":r.id,"email":r.email} for r in db.scalars(select(NotificationRecipient).order_by(NotificationRecipient.email)).all()]

@app.post("/api/admin/notification-recipients")
def add_recipient(data:RecipientIn,_:User=Depends(admin),db:Session=Depends(db_session)):
    email=data.email.lower()
    if db.scalar(select(NotificationRecipient).where(NotificationRecipient.email==email)): raise HTTPException(409,"Recipient already added")
    row=NotificationRecipient(email=email); db.add(row); db.commit(); return {"id":row.id,"email":email}

@app.delete("/api/admin/notification-recipients/{recipient_id}")
def delete_recipient(recipient_id:int,_:User=Depends(admin),db:Session=Depends(db_session)):
    row=db.get(NotificationRecipient,recipient_id)
    if not row: raise HTTPException(404,"Recipient not found")
    db.delete(row);db.commit();return {"ok":True}

@app.get("/api/activities")
def list_activities(user:User=Depends(current_user),db:Session=Depends(db_session)):
    activities=db.scalars(select(Activity).order_by(Activity.activity_date.desc())).all()
    output=[]
    today=datetime.now(PERTH).date()
    is_staff=user.role in ("admin","tenant_admin")
    for a in activities:
        poll=db.scalar(select(Poll).where(Poll.activity_id==a.id))
        completed=a.activity_date<today
        item={"id":a.id,"title":a.title,"date":a.activity_date,"completed":completed,"poll":None}
        if not completed:
            item["description"]=a.description
        if poll:
            options=db.scalars(select(PollOption).where(PollOption.poll_id==poll.id)).all()
            vote=db.scalar(select(Vote).where(Vote.poll_id==poll.id,Vote.user_id==user.id))
            labels={o.id:o.label for o in options}
            if completed:
                if not is_staff and not vote:
                    continue
                if vote:
                    submitted=vote.created_at
                    if submitted.tzinfo is None: submitted=submitted.replace(tzinfo=timezone.utc)
                    item["my_vote"]={"choice":labels.get(vote.option_id,"Unknown option"),"submitted_on":submitted.astimezone(PERTH).date()}
                if is_staff:
                    counts={option_id:count for option_id,count in db.execute(select(Vote.option_id,func.count()).where(Vote.poll_id==poll.id).group_by(Vote.option_id))}
                    item["poll"]={"question":poll.question,"summary":[{"label":o.label,"votes":counts.get(o.id,0)} for o in options],"total_votes":sum(counts.values())}
            else:
                item["poll"]={"id":poll.id,"question":poll.question,"voted_option_id":vote.option_id if vote else None,"options":[{"id":o.id,"label":o.label,"votes":db.scalar(select(func.count()).select_from(Vote).where(Vote.option_id==o.id)) if is_staff else None} for o in options]}
            if is_staff:
                voters={v.user_id:v.option_id for v in db.scalars(select(Vote).where(Vote.poll_id==poll.id))}
                tenants=db.scalars(select(Tenant).where(Tenant.account_role!="admin").order_by(Tenant.full_name)).all()
                item["poll"]["participation"]=[{"tenant_id":t.id,"name":t.full_name,
                    "active":t.is_active,"choice":labels.get(voters[t.user_id]) if t.user_id in voters else None} for t in tenants]
        elif completed and not is_staff:
            continue
        output.append(item)
    return output

@app.post("/api/admin/activities")
def add_activity(data:ActivityIn,tasks:BackgroundTasks,user:User=Depends(admin),db:Session=Depends(db_session)):
    activity=Activity(title=data.title,description=data.description,activity_date=data.activity_date,created_by=user.id)
    db.add(activity); db.flush()
    if data.poll_question and len(data.options)>=2:
        poll=Poll(activity_id=activity.id,question=data.poll_question); db.add(poll); db.flush()
        db.add_all([PollOption(poll_id=poll.id,label=x.strip()) for x in data.options if x.strip()])
    db.commit()
    tenants=db.scalars(select(Tenant).where(Tenant.is_active==True,Tenant.account_role!="admin")).all()
    for t in tenants:
        notify_calendar(db,tasks,t,"activity",activity.id,"Activity: "+data.title,data.activity_date,
            f"{data.description}\nActivity date: {data.activity_date}. Add the attached event to your calendar and sign in to vote.",staff_copy=False)
    notify(db,tasks,[],"Activity published: "+data.title,f"Scheduled on {data.activity_date}: {data.title}.")
    return {"id":activity.id}

@app.post("/api/internal/send-reminders")
def send_reminders(authorization:Optional[str]=Header(default=None),db:Session=Depends(db_session)):
    expected=os.getenv("REMINDER_SECRET","")
    if not expected or not authorization or not secrets.compare_digest(authorization,"Bearer "+expected):
        raise HTTPException(403,"Not allowed")
    if not os.getenv("RESEND_API_KEY") or not os.getenv("EMAIL_FROM"):
        raise HTTPException(503,"Email is not configured")
    # A scheduled GitHub Actions request wakes the free Render backend each day.
    tomorrow=datetime.now(PERTH).date()+timedelta(days=1)
    # Serialize concurrent schedule/manual runs on Postgres to avoid repeat sends.
    if engine.dialect.name=="postgresql": db.execute(text("SELECT pg_advisory_xact_lock(71829004)"))
    sent=0; failed=0
    for a in db.scalars(select(Activity).where(Activity.activity_date==tomorrow)).all():
        for t in db.scalars(select(Tenant).where(Tenant.is_active==True,Tenant.account_role!="admin")).all():
            key=("activity",a.id,t.id)
            if db.scalar(select(ReminderDelivery.id).where(ReminderDelivery.kind==key[0],ReminderDelivery.item_id==key[1],ReminderDelivery.tenant_id==key[2])): continue
            if send_email([t.email],"Tomorrow: "+a.title,f"Reminder: {a.title} is tomorrow, {tomorrow}. {a.description}"):
                db.add(ReminderDelivery(kind=key[0],item_id=key[1],tenant_id=key[2])); db.flush(); sent+=1
            else: failed+=1
    for c,t in db.execute(select(RentCharge,Tenant).join(Tenant,RentCharge.tenant_id==Tenant.id).where(RentCharge.due_date==tomorrow,Tenant.is_active==True,RentCharge.amount>RentCharge.amount_paid)).all():
        key=("rent",c.id,t.id)
        if db.scalar(select(ReminderDelivery.id).where(ReminderDelivery.kind==key[0],ReminderDelivery.item_id==key[1],ReminderDelivery.tenant_id==key[2])): continue
        due=c.amount-c.amount_paid
        if send_email([t.email],"Rent due tomorrow",f"Hi {t.full_name}, AUD {due:.2f} is due tomorrow, {tomorrow}. Please sign in to view your balance."):
            db.add(ReminderDelivery(kind=key[0],item_id=key[1],tenant_id=key[2])); db.flush(); sent+=1
        else: failed+=1
    db.commit()
    if failed: raise HTTPException(503,f"{sent} reminders sent; {failed} failed and will be retried")
    return {"date":tomorrow,"sent":sent}

@app.post("/api/internal/prune-payments")
def prune_payments(authorization:Optional[str]=Header(default=None),db:Session=Depends(db_session)):
    expected=os.getenv("REMINDER_SECRET","")
    if not expected or not authorization or not secrets.compare_digest(authorization,"Bearer "+expected):
        raise HTTPException(403,"Not allowed")
    cutoff=datetime.now(timezone.utc)-timedelta(days=365)
    if engine.dialect.name=="postgresql": db.execute(text("SELECT pg_advisory_xact_lock(71829005)"))
    submissions=db.scalars(select(PaymentSubmission).where(PaymentSubmission.submitted_at<cutoff)).all()
    manual=db.scalars(select(ManualPayment).where(ManualPayment.created_at<cutoff)).all()
    # Keep compact tenant/year totals for collection reports. Charge balances live in rent_charges.
    totals={}
    for p in submissions:
        if p.state=="approved": totals[(p.tenant_id,p.payment_date.year)]=totals.get((p.tenant_id,p.payment_date.year),Decimal("0.00"))+p.amount
    for p in manual:
        totals[(p.tenant_id,p.payment_date.year)]=totals.get((p.tenant_id,p.payment_date.year),Decimal("0.00"))+p.amount
    for (tenant_id,year),amount in totals.items():
        row=db.get(ArchivedCollection,(tenant_id,year))
        if row: row.amount+=amount
        else: db.add(ArchivedCollection(tenant_id=tenant_id,year=year,amount=amount))
    for p in submissions: db.delete(p)
    for p in manual: db.delete(p)
    db.commit()
    return {"deleted_submissions":len(submissions),"deleted_manual_payments":len(manual),"cutoff":cutoff}

@app.post("/api/polls/{poll_id}/vote")
def vote(poll_id:int,data:VoteIn,tasks:BackgroundTasks,user:User=Depends(current_user),db:Session=Depends(db_session)):
    if user.role not in ("tenant","tenant_admin"): raise HTTPException(403,"Only tenants can vote")
    poll=db.get(Poll,poll_id); option=db.get(PollOption,data.option_id)
    if not poll or not poll.is_active or not option or option.poll_id!=poll_id: raise HTTPException(400,"Invalid poll option")
    activity=db.get(Activity,poll.activity_id)
    if not activity or activity.activity_date<datetime.now(PERTH).date(): raise HTTPException(409,"Voting has closed for this activity")
    if db.scalar(select(Vote).where(Vote.poll_id==poll_id,Vote.user_id==user.id)): raise HTTPException(409,"You have already voted")
    db.add(Vote(poll_id=poll_id,option_id=data.option_id,user_id=user.id)); db.commit()
    notify(db,tasks,[user.email],"Activity vote received",f"A vote was submitted for activity poll #{poll_id}. Sign in to see the poll.")
    return {"ok":True}
