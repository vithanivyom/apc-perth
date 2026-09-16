import os
import logging
import json
import urllib.request
import hashlib
import secrets
from decimal import Decimal
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI, Form, HTTPException, UploadFile, File, status
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, LargeBinary, Numeric, String, Text, UniqueConstraint, create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://haven:haven@db:5432/haven")
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-before-production")
ALGORITHM = "HS256"
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com").lower()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "ChangeMe123!")

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

def invite_tenant(db:Session,tasks:BackgroundTasks,tenant:Tenant):
    if not os.getenv("RESEND_API_KEY") or not os.getenv("EMAIL_FROM"):
        raise HTTPException(503,"Email is not configured. Set RESEND_API_KEY and EMAIL_FROM first.")
    if tenant.user_id: raise HTTPException(409,"Tenant account already registered")
    code=secrets.token_urlsafe(32)
    row=db.get(RegistrationInvite,tenant.id)
    if row is None:
        row=RegistrationInvite(tenant_id=tenant.id,token_hash="",expires_at=datetime.now(timezone.utc))
        db.add(row)
    row.token_hash=hashlib.sha256(code.encode()).hexdigest()
    row.expires_at=datetime.now(timezone.utc)+timedelta(days=7)
    db.commit()
    tasks.add_task(send_email,[tenant.email],"Your chhatralay registration code",f"Your one-time registration code is: {code}\nIt expires in 7 days. Use it when creating your tenant account. If you did not expect this email, contact the administrator.")

def send_email(recipients: list[str], subject: str, body: str):
    key = os.getenv("RESEND_API_KEY", "")
    sender = os.getenv("EMAIL_FROM", "")
    if not key or not sender:
        logging.warning("Email not configured: set RESEND_API_KEY and EMAIL_FROM")
        return
    for recipient in set(x.lower() for x in recipients if x):
        try:
            request=urllib.request.Request("https://api.resend.com/emails",
                data=json.dumps({"from":sender,"to":[recipient],"subject":subject,"text":body}).encode(),
                headers={"Authorization":"Bearer "+key,"Content-Type":"application/json","User-Agent":"apc-perth/1.0"},method="POST")
            with urllib.request.urlopen(request, timeout=15) as response:
                if response.status>=300: raise RuntimeError("Email provider rejected request")
        except Exception:
            logging.exception("Notification delivery failed for %s", recipient)

def notify(db: Session, tasks: BackgroundTasks, recipients: list[str], subject: str, body: str):
    extra = db.scalars(select(NotificationRecipient)).all()
    admins=db.scalars(select(User).where(User.role=="admin",User.is_active==True)).all()
    tasks.add_task(send_email, recipients + [a.email for a in admins] + [r.email for r in extra], subject, body)

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
    return jwt.encode({"sub": str(user.id), "role": user.role, "exp": datetime.now(timezone.utc)+timedelta(hours=12)}, SECRET_KEY, algorithm=ALGORITHM)

def current_user(token: str=Depends(oauth2), db: Session=Depends(db_session)):
    try: user_id = int(jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])["sub"])
    except (JWTError, KeyError, ValueError): raise HTTPException(401, "Invalid or expired login")
    user = db.get(User, user_id)
    if not user or not user.is_active: raise HTTPException(401, "Account unavailable")
    return user

def admin(user: User=Depends(current_user)):
    if user.role != "admin": raise HTTPException(403, "Admin access required")
    return user

class RegisterIn(BaseModel):
    full_name: str
    email: EmailStr
    password: str = Field(min_length=8)
    invite_code: str
class TenantIn(BaseModel):
    full_name: str; email: EmailStr; phone: str=""; current_address: str=""; room: str
    move_in_date: date; weekly_rent: float=Field(gt=0); bond_amount: float=0
    reference_name: str=""; reference_phone: str=""; reference_email: str=""
class ChargeIn(BaseModel):
    tenant_id: int; due_date: date; amount: float=Field(gt=0); note: str=""
class BulkChargeIn(BaseModel):
    due_date: date
class PaymentIn(BaseModel):
    amount_paid: float=Field(ge=0)
class ActivityIn(BaseModel):
    title: str; description: str=""; activity_date: date; poll_question: Optional[str]=None; options: list[str]=[]
class VoteIn(BaseModel):
    option_id: int
class ReviewIn(BaseModel):
    decision: str
    note: str = Field(default="", max_length=300)
class RecipientIn(BaseModel):
    email: EmailStr
class PasswordChangeIn(BaseModel):
    old_password: str
    new_password: str = Field(min_length=12)

@app.on_event("startup")
def startup():
    Base.metadata.create_all(engine)
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
    if not tenant: raise HTTPException(403,"Ask the administrator to add your tenant email first")
    if tenant.user_id: raise HTTPException(409,"This tenant account is already registered")
    invite=db.get(RegistrationInvite,tenant.id)
    expires=invite.expires_at if invite else None
    if expires and expires.tzinfo is None: expires=expires.replace(tzinfo=timezone.utc)
    if not invite or expires < datetime.now(timezone.utc) or not secrets.compare_digest(invite.token_hash,hashlib.sha256(data.invite_code.encode()).hexdigest()):
        raise HTTPException(403,"Invalid or expired registration code. Ask the admin to resend it.")
    user=User(email=email,full_name=data.full_name,password_hash=pwd.hash(data.password),role="tenant")
    db.add(user); db.flush(); tenant.user_id=user.id; db.delete(invite); db.commit()
    notify(db,tasks,[tenant.email],"Tenant account created",f"{tenant.full_name} registered their tenant account.")
    return {"access_token":token_for(user),"token_type":"bearer","role":"tenant"}

@app.post("/api/auth/login")
def login(form:OAuth2PasswordRequestForm=Depends(), db:Session=Depends(db_session)):
    user=db.scalar(select(User).where(func.lower(User.email)==form.username.lower()))
    if not user or not pwd.verify(form.password,user.password_hash): raise HTTPException(401,"Incorrect email or password")
    return {"access_token":token_for(user),"token_type":"bearer","role":user.role,"name":user.full_name}

@app.post("/api/me/change-password")
def change_password(data:PasswordChangeIn,user:User=Depends(current_user),db:Session=Depends(db_session)):
    if not pwd.verify(data.old_password,user.password_hash): raise HTTPException(403,"Current password is incorrect")
    user.password_hash=pwd.hash(data.new_password)
    db.commit()
    return {"ok":True}

@app.get("/api/me")
def me(user:User=Depends(current_user),db:Session=Depends(db_session)):
    base={"id":user.id,"name":user.full_name,"email":user.email,"role":user.role}
    if user.role=="tenant":
        tenant=db.scalar(select(Tenant).where(Tenant.user_id==user.id))
        if tenant:
            charges=db.scalars(select(RentCharge).where(RentCharge.tenant_id==tenant.id).order_by(RentCharge.due_date.desc())).all()
            base["tenant"]={"id":tenant.id,"room":tenant.room,"weekly_rent":float(tenant.weekly_rent),"balance":sum(float(c.amount)-float(c.amount_paid) for c in charges),"charges":[{"id":c.id,"due_date":c.due_date,"amount":float(c.amount),"paid":float(c.amount_paid),"balance":float(c.amount)-float(c.amount_paid)} for c in charges]}
    return base

@app.get("/api/admin/dashboard")
def dashboard(_:User=Depends(admin),db:Session=Depends(db_session)):
    tenants=db.scalars(select(Tenant).where(Tenant.is_active==True).order_by(Tenant.full_name)).all()
    rows=[]
    for t in tenants:
        charges=db.scalars(select(RentCharge).where(RentCharge.tenant_id==t.id)).all()
        balance=sum(float(c.amount)-float(c.amount_paid) for c in charges)
        rows.append({"id":t.id,"name":t.full_name,"email":t.email,"room":t.room,"registered":bool(t.user_id),"weekly_rent":float(t.weekly_rent),"balance":balance})
    return {"tenants":rows,"pending":[r for r in rows if r["balance"]>0],"total_outstanding":sum(r["balance"] for r in rows)}

@app.get("/api/admin/tenants/{tenant_id}")
def tenant_details(tenant_id:int,_:User=Depends(admin),db:Session=Depends(db_session)):
    tenant=db.get(Tenant,tenant_id)
    if not tenant: raise HTTPException(404,"Tenant not found")
    charges=db.scalars(select(RentCharge).where(RentCharge.tenant_id==tenant_id).order_by(RentCharge.due_date.desc(),RentCharge.id.desc())).all()
    payments=db.scalars(select(PaymentSubmission).where(PaymentSubmission.tenant_id==tenant_id).order_by(PaymentSubmission.id.desc())).all()
    return {"id":tenant.id,"full_name":tenant.full_name,"email":tenant.email,"phone":tenant.phone,
            "current_address":tenant.current_address,"room":tenant.room,"move_in_date":tenant.move_in_date,
            "weekly_rent":float(tenant.weekly_rent),"bond_amount":float(tenant.bond_amount),
            "reference_name":tenant.reference_name,"reference_phone":tenant.reference_phone,
            "reference_email":tenant.reference_email,"is_active":tenant.is_active,"registered":bool(tenant.user_id),
            "charges":[{"id":c.id,"due_date":c.due_date,"amount":float(c.amount),"paid":float(c.amount_paid),"note":c.note} for c in charges],
            "payments":[payment_json(p,tenant) for p in payments]}

@app.post("/api/admin/tenants")
def add_tenant(data:TenantIn,tasks:BackgroundTasks,_:User=Depends(admin),db:Session=Depends(db_session)):
    if not os.getenv("RESEND_API_KEY") or not os.getenv("EMAIL_FROM"):
        raise HTTPException(503,"Email is not configured. Set RESEND_API_KEY and EMAIL_FROM first.")
    if db.scalar(select(Tenant).where(func.lower(Tenant.email)==data.email.lower())): raise HTTPException(409,"Tenant email already exists")
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

@app.post("/api/admin/charges")
def add_charge(data:ChargeIn,tasks:BackgroundTasks,_:User=Depends(admin),db:Session=Depends(db_session)):
    tenant=db.get(Tenant,data.tenant_id)
    if not tenant: raise HTTPException(404,"Tenant not found")
    charge=RentCharge(**data.model_dump()); db.add(charge); db.commit()
    notify(db,tasks,[tenant.email],"Rent charge added",f"A rent charge of AUD {data.amount:.2f} was added for {tenant.full_name}. Sign in to see your balance.")
    return {"id":charge.id}

@app.post("/api/admin/charges/all")
def charge_all(data:BulkChargeIn,tasks:BackgroundTasks,_:User=Depends(admin),db:Session=Depends(db_session)):
    tenants=db.scalars(select(Tenant).where(Tenant.is_active==True).order_by(Tenant.id)).all()
    if not tenants: raise HTTPException(400,"Add an active tenant first")
    if db.get(BulkRentRun,data.due_date): raise HTTPException(409,"Rent charges for this date were already created for all tenants")
    db.add(BulkRentRun(due_date=data.due_date))
    db.add_all([RentCharge(tenant_id=t.id,due_date=data.due_date,amount=t.weekly_rent,
                           note="Rent due on "+data.due_date.isoformat()) for t in tenants])
    try: db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,"Rent charges for this date were already created for all tenants")
    for t in tenants:
        notify(db,tasks,[t.email],"Rent due on "+data.due_date.isoformat(),
               f"Hi {t.full_name}, your rent of AUD {t.weekly_rent:.2f} is due on {data.due_date}. Sign in to view your balance.")
    return {"created":len(tenants),"due_date":data.due_date}

@app.patch("/api/admin/charges/{charge_id}")
def record_payment(charge_id:int,data:PaymentIn,tasks:BackgroundTasks,_:User=Depends(admin),db:Session=Depends(db_session)):
    charge=db.get(RentCharge,charge_id)
    if not charge: raise HTTPException(404,"Charge not found")
    if Decimal(str(data.amount_paid))>charge.amount: raise HTTPException(400,"Amount paid exceeds charge")
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
    if user.role!="tenant": raise HTTPException(403,"Tenant access required")
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
    for a in activities:
        poll=db.scalar(select(Poll).where(Poll.activity_id==a.id))
        item={"id":a.id,"title":a.title,"description":a.description,"date":a.activity_date,"poll":None}
        if poll:
            options=db.scalars(select(PollOption).where(PollOption.poll_id==poll.id)).all()
            vote=db.scalar(select(Vote).where(Vote.poll_id==poll.id,Vote.user_id==user.id))
            item["poll"]={"id":poll.id,"question":poll.question,"voted_option_id":vote.option_id if vote else None,"options":[{"id":o.id,"label":o.label,"votes":db.scalar(select(func.count()).select_from(Vote).where(Vote.option_id==o.id)) if user.role=="admin" else None} for o in options]}
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
    tenants=db.scalars(select(Tenant).where(Tenant.is_active==True)).all()
    notify(db,tasks,[t.email for t in tenants],"New activity: "+data.title,f"A new activity, {data.title}, is scheduled for {data.activity_date}. Sign in to see details and vote if a poll is available.")
    return {"id":activity.id}

@app.post("/api/polls/{poll_id}/vote")
def vote(poll_id:int,data:VoteIn,tasks:BackgroundTasks,user:User=Depends(current_user),db:Session=Depends(db_session)):
    if user.role!="tenant": raise HTTPException(403,"Only tenants can vote")
    poll=db.get(Poll,poll_id); option=db.get(PollOption,data.option_id)
    if not poll or not poll.is_active or not option or option.poll_id!=poll_id: raise HTTPException(400,"Invalid poll option")
    if db.scalar(select(Vote).where(Vote.poll_id==poll_id,Vote.user_id==user.id)): raise HTTPException(409,"You have already voted")
    db.add(Vote(poll_id=poll_id,option_id=data.option_id,user_id=user.id)); db.commit()
    notify(db,tasks,[user.email],"Activity vote received",f"A vote was submitted for activity poll #{poll_id}. Sign in to see the poll.")
    return {"ok":True}
