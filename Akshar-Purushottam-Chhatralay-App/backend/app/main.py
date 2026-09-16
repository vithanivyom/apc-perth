import os
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, create_engine, func, select
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
class TenantIn(BaseModel):
    full_name: str; email: EmailStr; phone: str=""; current_address: str=""; room: str
    move_in_date: date; weekly_rent: float=Field(gt=0); bond_amount: float=0
    reference_name: str=""; reference_phone: str=""; reference_email: str=""
class ChargeIn(BaseModel):
    tenant_id: int; due_date: date; amount: float=Field(gt=0); note: str=""
class PaymentIn(BaseModel):
    amount_paid: float=Field(ge=0)
class ActivityIn(BaseModel):
    title: str; description: str=""; activity_date: date; poll_question: Optional[str]=None; options: list[str]=[]
class VoteIn(BaseModel):
    option_id: int

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
def register(data:RegisterIn, db:Session=Depends(db_session)):
    email=data.email.lower()
    tenant=db.scalar(select(Tenant).where(func.lower(Tenant.email)==email))
    if not tenant: raise HTTPException(403,"Ask the administrator to add your tenant email first")
    if tenant.user_id: raise HTTPException(409,"This tenant account is already registered")
    user=User(email=email,full_name=data.full_name,password_hash=pwd.hash(data.password),role="tenant")
    db.add(user); db.flush(); tenant.user_id=user.id; db.commit()
    return {"access_token":token_for(user),"token_type":"bearer","role":"tenant"}

@app.post("/api/auth/login")
def login(form:OAuth2PasswordRequestForm=Depends(), db:Session=Depends(db_session)):
    user=db.scalar(select(User).where(func.lower(User.email)==form.username.lower()))
    if not user or not pwd.verify(form.password,user.password_hash): raise HTTPException(401,"Incorrect email or password")
    return {"access_token":token_for(user),"token_type":"bearer","role":user.role,"name":user.full_name}

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
        rows.append({"id":t.id,"name":t.full_name,"email":t.email,"room":t.room,"weekly_rent":float(t.weekly_rent),"balance":balance})
    return {"tenants":rows,"pending":[r for r in rows if r["balance"]>0],"total_outstanding":sum(r["balance"] for r in rows)}

@app.post("/api/admin/tenants")
def add_tenant(data:TenantIn,_:User=Depends(admin),db:Session=Depends(db_session)):
    if db.scalar(select(Tenant).where(func.lower(Tenant.email)==data.email.lower())): raise HTTPException(409,"Tenant email already exists")
    tenant=Tenant(**data.model_dump()); tenant.email=data.email.lower(); db.add(tenant); db.commit(); db.refresh(tenant)
    return {"id":tenant.id}

@app.post("/api/admin/charges")
def add_charge(data:ChargeIn,_:User=Depends(admin),db:Session=Depends(db_session)):
    if not db.get(Tenant,data.tenant_id): raise HTTPException(404,"Tenant not found")
    charge=RentCharge(**data.model_dump()); db.add(charge); db.commit(); return {"id":charge.id}

@app.patch("/api/admin/charges/{charge_id}")
def record_payment(charge_id:int,data:PaymentIn,_:User=Depends(admin),db:Session=Depends(db_session)):
    charge=db.get(RentCharge,charge_id)
    if not charge: raise HTTPException(404,"Charge not found")
    charge.amount_paid=data.amount_paid; db.commit(); return {"ok":True}

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
def add_activity(data:ActivityIn,user:User=Depends(admin),db:Session=Depends(db_session)):
    activity=Activity(title=data.title,description=data.description,activity_date=data.activity_date,created_by=user.id)
    db.add(activity); db.flush()
    if data.poll_question and len(data.options)>=2:
        poll=Poll(activity_id=activity.id,question=data.poll_question); db.add(poll); db.flush()
        db.add_all([PollOption(poll_id=poll.id,label=x.strip()) for x in data.options if x.strip()])
    db.commit(); return {"id":activity.id}

@app.post("/api/polls/{poll_id}/vote")
def vote(poll_id:int,data:VoteIn,user:User=Depends(current_user),db:Session=Depends(db_session)):
    if user.role!="tenant": raise HTTPException(403,"Only tenants can vote")
    poll=db.get(Poll,poll_id); option=db.get(PollOption,data.option_id)
    if not poll or not poll.is_active or not option or option.poll_id!=poll_id: raise HTTPException(400,"Invalid poll option")
    if db.scalar(select(Vote).where(Vote.poll_id==poll_id,Vote.user_id==user.id)): raise HTTPException(409,"You have already voted")
    db.add(Vote(poll_id=poll_id,option_id=data.option_id,user_id=user.id)); db.commit(); return {"ok":True}
