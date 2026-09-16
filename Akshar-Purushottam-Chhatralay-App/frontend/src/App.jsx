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
  <button className={page==="payments"?"active":""} onClick={()=>setPage("payments")}><WalletCards/>Payments</button>
  {user.role==="admin"&&<button className={page==="tenants"?"active":""} onClick={()=>setPage("tenants")}><Users/>Add tenant</button>}
  {user.role==="admin"&&<button className={page==="recipients"?"active":""} onClick={()=>setPage("recipients")}><Bell/>Email recipients</button>}
 </nav><button onClick={logout}><LogOut/>Sign out</button></aside>
 <main><header><div><small>{user.role.toUpperCase()}</small><h1>Welcome, {user.name}</h1></div><Bell/></header>
 {error&&<div className="error">{error}</div>}
 {page==="activities"?<Activities user={user} setError={setError}/>:page==="tenants"?<AddTenant setError={setError}/>:page==="payments"?<Payments user={user} setError={setError} reloadUser={load}/>:page==="recipients"?<Recipients setError={setError}/>:user.role==="admin"?<AdminDashboard/>:<TenantDashboard user={user}/>}
 </main></div>
}

function Login({onDone}){
 const [register,setRegister]=useState(false),[error,setError]=useState("");
 async function submit(e){e.preventDefault();const f=new FormData(e.currentTarget);let r;
  if(register)r=await fetch(API+"/api/auth/register",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(Object.fromEntries(f))});
  else{const body=new URLSearchParams();body.set("username",f.get("email"));body.set("password",f.get("password"));r=await fetch(API+"/api/auth/login",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},body})}
  const d=await r.json();if(!r.ok)return setError(d.detail||"Could not sign in");localStorage.setItem("token",d.access_token);onDone()}
 return <div className="login"><div className="login-card"><div className="brand"><Home/> Akshar Purushottam Chhatralay</div><h1>{register?"Create tenant account":"Sign in"}</h1><p>{register?"Use the email and one-time registration code sent by your housing administrator.":"View rent, activities and voting."}</p>{error&&<div className="error">{error}</div>}<form onSubmit={submit}>{register&&<Field name="full_name" label="Full name" autoComplete="name"/>}<Field name="email" label="Email" type="email" autoComplete="email"/><Field name="password" label="Password" type="password" autoComplete={register?"new-password":"current-password"}/>{register&&<Field name="invite_code" label="Registration code from email" autoComplete="off"/>}<button className="primary">{register?"Create account":"Sign in"}</button></form><button className="link" onClick={()=>{setRegister(!register);setError("")}}>{register?"Already registered? Sign in":"Tenant? Create your account"}</button></div></div>
}
const Field=({name,label,type="text",...p})=><label>{label}<input name={name} type={type} required {...p}/></label>;

function TenantDashboard({user}){
 const t=user.tenant;if(!t)return <Empty title="Your tenant profile is not linked" text="Ask the administrator to check the email on your resident record."/>;
 return <><div className="cards"><Card title="Outstanding balance" value={aud(t.balance)} tone={t.balance>0?"warn":"ok"}/><Card title="Weekly rent" value={aud(t.weekly_rent)}/><Card title="Room" value={t.room}/></div><section><h2>Your rent history</h2>{!t.charges.length?<Empty title="No rent charges yet" text="New charges will appear here."/>:<table><thead><tr><th>Due date</th><th>Charge</th><th>Paid</th><th>Balance</th></tr></thead><tbody>{t.charges.map(c=><tr key={c.id}><td>{c.due_date}</td><td>{aud(c.amount)}</td><td>{aud(c.paid)}</td><td className={c.balance>0?"due":""}>{aud(c.balance)}</td></tr>)}</tbody></table>}</section></>
}
function AdminDashboard(){
 const [d,setD]=useState(null);const load=()=>fetch(API+"/api/admin/dashboard",{headers:auth()}).then(r=>r.json()).then(setD);
 async function resend(tenant){const r=await fetch(API+`/api/admin/tenants/${tenant.id}/invite`,{method:"POST",headers:auth()});const data=await r.json();alert(r.ok?`Registration code emailed to ${tenant.email}`:(data.detail||"Could not send code"))}
 useEffect(() => {
  void load();
}, []);
 if(!d)return <div>Loading…</div>;return <><div className="cards"><Card title="Total tenants" value={d.tenants.length}/><Card title="Tenants with outstanding rent" value={d.pending.length} tone="warn"/><Card title="Total outstanding" value={aud(d.total_outstanding)} tone="warn"/></div><section><h2>All tenants</h2><table><thead><tr><th>Tenant</th><th>Room</th><th>Email</th><th>Outstanding</th><th>Registration</th></tr></thead><tbody>{d.tenants.map(x=><tr key={x.id}><td>{x.name}</td><td>{x.room}</td><td>{x.email}</td><td className={x.balance>0?"due":""}>{aud(x.balance)}</td><td>{x.registered?"Registered":<button className="link" onClick={()=>resend(x)}>Email code</button>}</td></tr>)}</tbody></table></section><ChargeForm tenants={d.tenants} reload={load}/></>
}
function ChargeForm({tenants,reload}){async function submit(e){e.preventDefault();const form=e.currentTarget;const f=new FormData(form);const r=await fetch(API+"/api/admin/charges",{method:"POST",headers:{...auth(),"Content-Type":"application/json"},body:JSON.stringify({tenant_id:+f.get("tenant_id"),due_date:f.get("due_date"),amount:+f.get("amount"),note:f.get("note")})});if(r.ok){form.reset();reload()}}
 return <section><h2>Add rent charge</h2><form className="grid-form" onSubmit={submit}><label>Tenant<select name="tenant_id" required>{tenants.map(t=><option value={t.id} key={t.id}>{t.name} — {t.room}</option>)}</select></label><Field name="due_date" label="Due date" type="date"/><Field name="amount" label="Amount (AUD)" type="number" step="0.01"/><Field name="note" label="Note"/><button className="primary">Add charge</button></form></section>}

function AddTenant({setError}){async function submit(e){e.preventDefault();const form=e.currentTarget;const f=new FormData(form);const body=Object.fromEntries(f);body.weekly_rent=+body.weekly_rent;body.bond_amount=+body.bond_amount;const r=await fetch(API+"/api/admin/tenants",{method:"POST",headers:{...auth(),"Content-Type":"application/json"},body:JSON.stringify(body)});const d=await r.json();if(!r.ok)return setError(d.detail);form.reset();alert("Tenant added. A registration code will be emailed to them.")}
 return <section><h2>Add tenant</h2><p className="muted">A registration code will be emailed to this tenant. Configure the email API in the backend first.</p><form className="grid-form" onSubmit={submit}><Field name="full_name" label="Full name"/><Field name="email" label="Email" type="email"/><Field name="phone" label="Phone"/><Field name="room" label="Room / unit"/><Field name="current_address" label="Current address"/><Field name="move_in_date" label="Move-in date" type="date"/><Field name="weekly_rent" label="Weekly rent" type="number" step="0.01"/><Field name="bond_amount" label="Bond amount" type="number" step="0.01"/><Field name="reference_name" label="Reference name"/><Field name="reference_phone" label="Reference phone"/><Field name="reference_email" label="Reference email" type="email"/><button className="primary">Save tenant</button></form></section>}

function Activities({user,setError}){const [items,setItems]=useState([]);const load=()=>fetch(API+"/api/activities",{headers:auth()}).then(r=>r.json()).then(setItems);useEffect(() => {
  void load();
}, []);
 async function add(e){e.preventDefault();const form=e.currentTarget;const f=new FormData(form);const body={title:f.get("title"),description:f.get("description"),activity_date:f.get("activity_date"),poll_question:f.get("poll_question")||null,options:[f.get("option1"),f.get("option2"),f.get("option3")].filter(Boolean)};const r=await fetch(API+"/api/admin/activities",{method:"POST",headers:{...auth(),"Content-Type":"application/json"},body:JSON.stringify(body)});if(r.ok){form.reset();load()}}
 async function vote(poll,option){const r=await fetch(API+`/api/polls/${poll}/vote`,{method:"POST",headers:{...auth(),"Content-Type":"application/json"},body:JSON.stringify({option_id:option})});const d=await r.json();if(!r.ok)setError(d.detail);else load()}
 return <>{user.role==="admin"&&<section><h2>Post activity & poll</h2><form className="grid-form" onSubmit={add}><Field name="title" label="Activity title"/><Field name="activity_date" label="Date" type="date"/><Field name="description" label="Description"/><Field name="poll_question" label="Poll question (optional)"/><Field name="option1" label="Option 1"/><Field name="option2" label="Option 2"/><Field name="option3" label="Option 3 (optional)"/><button className="primary">Publish activity</button></form></section>}<section><h2>Activities</h2><div className="activity-list">{items.map(a=><article key={a.id}><div className="date">{a.date}</div><h3>{a.title}</h3><p>{a.description}</p>{a.poll&&<div className="poll"><strong>{a.poll.question}</strong>{a.poll.options.map(o=><button key={o.id} disabled={user.role!=="tenant"||!!a.poll.voted_option_id} onClick={()=>vote(a.poll.id,o.id)} className={a.poll.voted_option_id===o.id?"chosen":""}>{o.label}{user.role==="admin"&&` — ${o.votes} votes`}{a.poll.voted_option_id===o.id&&" ✓"}</button>)}</div>}</article>)}</div></section></>}

function Payments({user,setError,reloadUser}){
 const [items,setItems]=useState([]),[busy,setBusy]=useState(false);
 const endpoint=user.role==="admin"?"/api/admin/payments":"/api/payments";
 const load=async()=>{try{const r=await fetch(API+endpoint,{headers:auth()});if(!r.ok)throw Error("Could not load payments");setItems(await r.json())}catch(e){setError(e.message)}};
 useEffect(()=>{void load()},[endpoint]);
 async function submit(e){e.preventDefault();const form=e.currentTarget;const body=new FormData(form);const photo=body.get("receipt");if(photo?.size>2*1024*1024)return setError("Receipt must be under 2 MB");setBusy(true);setError("");try{
  const r=await fetch(API+"/api/payments",{method:"POST",headers:auth(),body});const data=await r.json();if(!r.ok)throw Error(data.detail||"Could not submit payment");form.reset();await load();
 }catch(e){setError(e.message)}finally{setBusy(false)}}
 async function review(p,decision){const note=decision==="rejected"?prompt("Reason for rejection (shown to tenant):"):"";if(note===null)return;setBusy(true);setError("");try{
  const r=await fetch(API+`/api/admin/payments/${p.id}/review`,{method:"POST",headers:{...auth(),"Content-Type":"application/json"},body:JSON.stringify({decision,note})});const data=await r.json();if(!r.ok)throw Error(data.detail||"Could not review payment");await load();await reloadUser();
 }catch(e){setError(e.message)}finally{setBusy(false)}}
 async function receipt(p){const tab=window.open("","_blank");if(!tab)return setError("Allow pop-ups to view the receipt");try{const r=await fetch(API+`/api/admin/payments/${p.id}/receipt`,{headers:auth()});if(!r.ok)throw Error("Could not open receipt");const url=URL.createObjectURL(await r.blob());tab.location.href=url;setTimeout(()=>URL.revokeObjectURL(url),60000)}catch(e){tab.close();setError(e.message)}}
 return <>{user.role==="tenant"&&<section><h2>Submit a rent payment</h2><p className="muted">Your tenant number is {user.tenant?.id}. Your balance changes after the admin verifies the transfer.</p><form className="grid-form" onSubmit={submit}><Field name="amount" label="Amount paid (AUD)" type="number" min="0.01" step="0.01"/><Field name="payment_date" label="Payment date" type="date"/><Field name="bank_reference" label="Bank transaction reference" maxLength="120"/><Field name="bank_details" label="Bank transfer details (optional; no account password)" required={false} maxLength="300"/><label>Receipt image (optional, JPG/PNG/WebP, max 2 MB)<input name="receipt" type="file" accept="image/jpeg,image/png,image/webp"/></label><button className="primary" disabled={busy}>Submit for review</button></form></section>}
 <section><h2>{user.role==="admin"?"Payment submissions":"My payment submissions"}</h2>{!items.length?<p className="muted">No payments submitted yet.</p>:<table><thead><tr>{user.role==="admin"&&<th>Tenant</th>}<th>Amount</th><th>Date</th><th>Bank reference</th><th>Details</th><th>Receipt</th><th>Status</th><th>Action</th></tr></thead><tbody>{items.map(p=><tr key={p.id}>{user.role==="admin"&&<td>{p.tenant_name} (#{p.tenant_id})</td>}<td>{aud(p.amount)}</td><td>{p.payment_date}</td><td>{p.bank_reference}</td><td>{p.bank_details}</td><td>{user.role==="admin"&&p.has_receipt?<button className="link" onClick={()=>receipt(p)}>View image</button>:p.has_receipt?"Attached":"—"}</td><td>{p.state}{p.review_note&&<small> — {p.review_note}</small>}</td><td>{user.role==="admin"&&p.state==="pending"?<div className="actions"><button disabled={busy} onClick={()=>review(p,"approved")}>Approve</button><button disabled={busy} onClick={()=>review(p,"rejected")}>Reject</button></div>:"—"}</td></tr>)}</tbody></table>}</section></>
}

function Recipients({setError}){
 const [items,setItems]=useState([]);
 const load=async()=>{try{const r=await fetch(API+"/api/admin/notification-recipients",{headers:auth()});if(!r.ok)throw Error("Could not load recipients");setItems(await r.json())}catch(e){setError(e.message)}};
 useEffect(()=>{void load()},[]);
 async function add(e){e.preventDefault();const form=e.currentTarget;const email=new FormData(form).get("email");setError("");try{const r=await fetch(API+"/api/admin/notification-recipients",{method:"POST",headers:{...auth(),"Content-Type":"application/json"},body:JSON.stringify({email})});const d=await r.json();if(!r.ok)throw Error(d.detail||"Could not add recipient");form.reset();await load()}catch(e){setError(e.message)}}
 async function remove(id){if(!confirm("Remove this email recipient?"))return;const r=await fetch(API+`/api/admin/notification-recipients/${id}`,{method:"DELETE",headers:auth()});if(r.ok)await load();else setError("Could not remove recipient")}
 async function changePassword(e){e.preventDefault();const form=e.currentTarget;const f=new FormData(form);setError("");try{const r=await fetch(API+"/api/me/change-password",{method:"POST",headers:{...auth(),"Content-Type":"application/json"},body:JSON.stringify({old_password:f.get("old_password"),new_password:f.get("new_password")})});const d=await r.json();if(!r.ok)throw Error(d.detail||"Could not change password");form.reset();alert("Password changed") }catch(e){setError(e.message)}}
 return <><section><h2>Additional email recipients</h2><p className="muted">Only add people authorized to receive tenant payment updates. Receipts are viewable by admins in the app and are never attached to email.</p><form className="grid-form" onSubmit={add}><Field name="email" label="Email address" type="email"/><button className="primary">Add recipient</button></form><table><tbody>{items.map(r=><tr key={r.id}><td>{r.email}</td><td><button className="link" onClick={()=>remove(r.id)}>Remove</button></td></tr>)}</tbody></table></section><section><h2>Change admin password</h2><form className="grid-form" onSubmit={changePassword}><Field name="old_password" label="Current password" type="password" autoComplete="current-password"/><Field name="new_password" label="New password (at least 12 characters)" type="password" minLength="12" autoComplete="new-password"/><button className="primary">Change password</button></form></section></>
}
const Card=({title,value,tone=""})=><div className={`card ${tone}`}><small>{title}</small><b>{value}</b></div>;
const Empty=({title,text})=><div className="empty"><CheckCircle2/><b>{title}</b><p>{text}</p></div>;
const aud=n=>new Intl.NumberFormat("en-AU",{style:"currency",currency:"AUD"}).format(n||0);
