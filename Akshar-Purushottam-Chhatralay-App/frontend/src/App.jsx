import {useEffect,useState} from "react";
import {Bell,CalendarDays,CheckCircle2,Home,LogOut,Plus,Users,WalletCards} from "lucide-react";
const API=import.meta.env.VITE_API_URL||"http://localhost:8000";
const auth=()=>({Authorization:`Bearer ${localStorage.getItem("token")}`});

export default function App(){
 const [user,setUser]=useState(null),[page,setPage]=useState("dashboard"),[error,setError]=useState("");
 const load=async()=>{const r=await fetch(API+"/api/me",{headers:auth()});if(r.ok)setUser(await r.json());else localStorage.removeItem("token")};
 useEffect(()=>{if(localStorage.getItem("token"))load()},[]);
 if(!localStorage.getItem("token"))return <Login onDone={load}/>;
 if(!user)return <div className="center">Loading your account…</div>;
 const logout=()=>{localStorage.removeItem("token");location.reload()};
 return <div className="shell"><aside><div className="brand"><Home/> Akshar Purushottam Chhatralay</div><nav>
  <button className={page==="dashboard"?"active":""} onClick={()=>setPage("dashboard")}><WalletCards/>Dashboard</button>
  <button className={page==="activities"?"active":""} onClick={()=>setPage("activities")}><CalendarDays/>Activities & votes</button>
  {user.role==="admin"&&<button className={page==="tenants"?"active":""} onClick={()=>setPage("tenants")}><Users/>Add tenant</button>}
 </nav><button onClick={logout}><LogOut/>Sign out</button></aside>
 <main><header><div><small>{user.role.toUpperCase()}</small><h1>Welcome, {user.name}</h1></div><Bell/></header>
 {error&&<div className="error">{error}</div>}
 {page==="activities"?<Activities user={user} setError={setError}/>:page==="tenants"?<AddTenant setError={setError}/>:user.role==="admin"?<AdminDashboard/>:<TenantDashboard user={user}/>}
 </main></div>
}

function Login({onDone}){
 const [register,setRegister]=useState(false),[error,setError]=useState("");
 async function submit(e){e.preventDefault();const f=new FormData(e.currentTarget);let r;
  if(register)r=await fetch(API+"/api/auth/register",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(Object.fromEntries(f))});
  else{const body=new URLSearchParams();body.set("username",f.get("email"));body.set("password",f.get("password"));r=await fetch(API+"/api/auth/login",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},body})}
  const d=await r.json();if(!r.ok)return setError(d.detail||"Could not sign in");localStorage.setItem("token",d.access_token);onDone()}
 return <div className="login"><div className="login-card"><div className="brand"><Home/> Akshar Purushottam Chhatralay</div><h1>{register?"Create tenant account":"Sign in"}</h1><p>{register?"Use the same email your housing administrator entered.":"View rent, activities and voting."}</p>{error&&<div className="error">{error}</div>}<form onSubmit={submit}>{register&&<Field name="full_name" label="Full name"/>}<Field name="email" label="Email" type="email"/><Field name="password" label="Password" type="password"/><button className="primary">{register?"Create account":"Sign in"}</button></form><button className="link" onClick={()=>{setRegister(!register);setError("")}}>{register?"Already registered? Sign in":"Tenant? Create your account"}</button></div></div>
}
const Field=({name,label,type="text",...p})=><label>{label}<input name={name} type={type} required {...p}/></label>;

function TenantDashboard({user}){
 const t=user.tenant;if(!t)return <Empty title="Your tenant profile is not linked" text="Ask the administrator to check the email on your resident record."/>;
 return <><div className="cards"><Card title="Outstanding balance" value={aud(t.balance)} tone={t.balance>0?"warn":"ok"}/><Card title="Weekly rent" value={aud(t.weekly_rent)}/><Card title="Room" value={t.room}/></div><section><h2>Your rent history</h2>{!t.charges.length?<Empty title="No rent charges yet" text="New charges will appear here."/>:<table><thead><tr><th>Due date</th><th>Charge</th><th>Paid</th><th>Balance</th></tr></thead><tbody>{t.charges.map(c=><tr key={c.id}><td>{c.due_date}</td><td>{aud(c.amount)}</td><td>{aud(c.paid)}</td><td className={c.balance>0?"due":""}>{aud(c.balance)}</td></tr>)}</tbody></table>}</section></>
}
function AdminDashboard(){
 const [d,setD]=useState(null);const load=()=>fetch(API+"/api/admin/dashboard",{headers:auth()}).then(r=>r.json()).then(setD);useEffect(() => {
  void load();
}, []);
 if(!d)return <div>Loading…</div>;return <><div className="cards"><Card title="Total tenants" value={d.tenants.length}/><Card title="Pending tenants" value={d.pending.length} tone="warn"/><Card title="Total outstanding" value={aud(d.total_outstanding)} tone="warn"/></div><section><h2>Pending rent</h2>{!d.pending.length?<Empty title="Everyone is up to date" text="No outstanding rent right now."/>:<table><thead><tr><th>Tenant</th><th>Room</th><th>Email</th><th>Outstanding</th></tr></thead><tbody>{d.pending.map(x=><tr key={x.id}><td>{x.name}</td><td>{x.room}</td><td>{x.email}</td><td className="due">{aud(x.balance)}</td></tr>)}</tbody></table>}</section><ChargeForm tenants={d.tenants} reload={load}/></>
}
function ChargeForm({tenants,reload}){async function submit(e){e.preventDefault();const f=new FormData(e.currentTarget);const r=await fetch(API+"/api/admin/charges",{method:"POST",headers:{...auth(),"Content-Type":"application/json"},body:JSON.stringify({tenant_id:+f.get("tenant_id"),due_date:f.get("due_date"),amount:+f.get("amount"),note:f.get("note")})});if(r.ok){e.currentTarget.reset();reload()}}
 return <section><h2>Add rent charge</h2><form className="grid-form" onSubmit={submit}><label>Tenant<select name="tenant_id" required>{tenants.map(t=><option value={t.id} key={t.id}>{t.name} — {t.room}</option>)}</select></label><Field name="due_date" label="Due date" type="date"/><Field name="amount" label="Amount (AUD)" type="number" step="0.01"/><Field name="note" label="Note"/><button className="primary">Add charge</button></form></section>}

function AddTenant({setError}){async function submit(e){e.preventDefault();const f=new FormData(e.currentTarget);const body=Object.fromEntries(f);body.weekly_rent=+body.weekly_rent;body.bond_amount=+body.bond_amount;const r=await fetch(API+"/api/admin/tenants",{method:"POST",headers:{...auth(),"Content-Type":"application/json"},body:JSON.stringify(body)});const d=await r.json();if(!r.ok)return setError(d.detail);e.currentTarget.reset();alert("Tenant added. They can now register with this email.")}
 return <section><h2>Add tenant</h2><p className="muted">This email becomes the tenant’s private login identity.</p><form className="grid-form" onSubmit={submit}><Field name="full_name" label="Full name"/><Field name="email" label="Email" type="email"/><Field name="phone" label="Phone"/><Field name="room" label="Room / unit"/><Field name="current_address" label="Current address"/><Field name="move_in_date" label="Move-in date" type="date"/><Field name="weekly_rent" label="Weekly rent" type="number" step="0.01"/><Field name="bond_amount" label="Bond amount" type="number" step="0.01"/><Field name="reference_name" label="Reference name"/><Field name="reference_phone" label="Reference phone"/><Field name="reference_email" label="Reference email" type="email"/><button className="primary">Save tenant</button></form></section>}

function Activities({user,setError}){const [items,setItems]=useState([]);const load=()=>fetch(API+"/api/activities",{headers:auth()}).then(r=>r.json()).then(setItems);useEffect(() => {
  void load();
}, []);
 async function add(e){e.preventDefault();const f=new FormData(e.currentTarget);const body={title:f.get("title"),description:f.get("description"),activity_date:f.get("activity_date"),poll_question:f.get("poll_question")||null,options:[f.get("option1"),f.get("option2"),f.get("option3")].filter(Boolean)};const r=await fetch(API+"/api/admin/activities",{method:"POST",headers:{...auth(),"Content-Type":"application/json"},body:JSON.stringify(body)});if(r.ok){e.currentTarget.reset();load()}}
 async function vote(poll,option){const r=await fetch(API+`/api/polls/${poll}/vote`,{method:"POST",headers:{...auth(),"Content-Type":"application/json"},body:JSON.stringify({option_id:option})});const d=await r.json();if(!r.ok)setError(d.detail);else load()}
 return <>{user.role==="admin"&&<section><h2>Post activity & poll</h2><form className="grid-form" onSubmit={add}><Field name="title" label="Activity title"/><Field name="activity_date" label="Date" type="date"/><Field name="description" label="Description"/><Field name="poll_question" label="Poll question (optional)"/><Field name="option1" label="Option 1"/><Field name="option2" label="Option 2"/><Field name="option3" label="Option 3 (optional)"/><button className="primary">Publish activity</button></form></section>}<section><h2>Activities</h2><div className="activity-list">{items.map(a=><article key={a.id}><div className="date">{a.date}</div><h3>{a.title}</h3><p>{a.description}</p>{a.poll&&<div className="poll"><strong>{a.poll.question}</strong>{a.poll.options.map(o=><button key={o.id} disabled={user.role!=="tenant"||!!a.poll.voted_option_id} onClick={()=>vote(a.poll.id,o.id)} className={a.poll.voted_option_id===o.id?"chosen":""}>{o.label}{user.role==="admin"&&` — ${o.votes} votes`}{a.poll.voted_option_id===o.id&&" ✓"}</button>)}</div>}</article>)}</div></section></>}
const Card=({title,value,tone=""})=><div className={`card ${tone}`}><small>{title}</small><b>{value}</b></div>;
const Empty=({title,text})=><div className="empty"><CheckCircle2/><b>{title}</b><p>{text}</p></div>;
const aud=n=>new Intl.NumberFormat("en-AU",{style:"currency",currency:"AUD"}).format(n||0);
