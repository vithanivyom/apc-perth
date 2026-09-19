import {useEffect,useState} from "react";
import {BarChart3,Bell,CalendarDays,CheckCircle2,FileText,Home,LogOut,Plus,Users,WalletCards} from "lucide-react";
const API=import.meta.env.VITE_API_URL||"http://localhost:8000";
const isAdmin=user=>user.role==="admin"||user.role==="tenant_admin";
const isTenant=user=>user.role==="tenant"||user.role==="tenant_admin";
const auth=()=>({Authorization:`Bearer ${localStorage.getItem("token")}`});
const IDLE_MS=15*60*1000;
const LAST_ACTIVITY="apc-last-activity",LAST_REFRESH="apc-last-refresh";
function clearLogin(){localStorage.removeItem("token");localStorage.removeItem(LAST_ACTIVITY);localStorage.removeItem(LAST_REFRESH)}

export default function App(){
 const [user,setUser]=useState(null),[page,setPage]=useState("dashboard"),[error,setError]=useState("");
 const [signedIn,setSignedIn]=useState(()=>!!localStorage.getItem("token")&&Date.now()-Number(localStorage.getItem(LAST_ACTIVITY)||0)<IDLE_MS);
 const logout=()=>{clearLogin();setSignedIn(false);setUser(null)};
 const load=async()=>{try{const r=await fetch(API+"/api/me",{headers:auth()});if(r.ok){setUser(await r.json());setSignedIn(true)}else logout()}catch{setError("Could not connect. Check the backend and try again.")}};
 useEffect(()=>{if(!signedIn)clearLogin();else if(localStorage.getItem("token"))void load()},[]);
 useEffect(()=>{if(!signedIn||!user)return;
  const expire=()=>{if(Date.now()-Number(localStorage.getItem(LAST_ACTIVITY)||0)>=IDLE_MS)logout()};
  const active=()=>{if(Date.now()-Number(localStorage.getItem(LAST_ACTIVITY)||0)>=IDLE_MS){logout();return}
   localStorage.setItem(LAST_ACTIVITY,String(Date.now()));
   if(Date.now()-Number(localStorage.getItem(LAST_REFRESH)||0)>4*60*1000){
    localStorage.setItem(LAST_REFRESH,String(Date.now()));
    void fetch(API+"/api/auth/refresh",{method:"POST",headers:auth()}).then(async r=>{
     if(!r.ok){logout();return}const d=await r.json();if(localStorage.getItem("token"))localStorage.setItem("token",d.access_token)
    }).catch(()=>{localStorage.removeItem(LAST_REFRESH)})
   }};
  const events=["pointerdown","keydown","touchstart","scroll"];
  events.forEach(name=>window.addEventListener(name,active,{passive:true}));
  const timer=window.setInterval(expire,10000);
  return()=>{window.clearInterval(timer);events.forEach(name=>window.removeEventListener(name,active))}
 },[signedIn,user?.id]);
 useEffect(()=>{window.scrollTo({top:0,behavior:"auto"});setError("")},[page]);
 if(!signedIn)return <Login onDone={load}/>;
 if(!user)return <div className="center">Loading your account…</div>;
 return <div className="shell"><aside><div className="brand"><Home/> Akshar Purushottam Chhatralay</div><nav>
  <button className={page==="dashboard"?"active":""} onClick={()=>setPage("dashboard")}><WalletCards/>Dashboard</button>
  <button className={page==="activities"?"active":""} onClick={()=>setPage("activities")}><CalendarDays/>Activities & votes</button>
  <button className={page==="payments"?"active":""} onClick={()=>setPage("payments")}><WalletCards/>Payments</button>
  {isAdmin(user)&&<button className={page==="collections"?"active":""} onClick={()=>setPage("collections")}><BarChart3/>Collections</button>}
  {isAdmin(user)&&<button className={page==="summary"?"active":""} onClick={()=>setPage("summary")}><FileText/>Summary</button>}
  {isAdmin(user)&&<button className={page==="tenants"?"active":""} onClick={()=>setPage("tenants")}><Users/>Tenants</button>}
  {isAdmin(user)&&<button className={page==="add-tenant"?"active":""} onClick={()=>setPage("add-tenant")}><Plus/>Add tenant</button>}
  {isTenant(user)&&<button className={page==="my-details"?"active":""} onClick={()=>setPage("my-details")}><Users/>My details</button>}
  {isAdmin(user)&&<button className={page==="recipients"?"active":""} onClick={()=>setPage("recipients")}><Bell/>Email recipients</button>}
 </nav><button onClick={logout} aria-label="Sign out"><LogOut/>Sign out</button></aside>
 <main><header><div><small>{user.role.toUpperCase()}</small><h1>Welcome, {user.name}</h1></div><Bell/></header>
 {error&&<div className="error">{error}</div>}
 {page==="activities"?<Activities user={user} setError={setError}/>:page==="tenants"&&isAdmin(user)?<Tenants setError={setError}/>:page==="add-tenant"&&isAdmin(user)?<AddTenant setError={setError}/>:page==="my-details"&&isTenant(user)?<MyDetails setError={setError}/>:page==="collections"&&isAdmin(user)?<Collections setError={setError}/>:page==="summary"&&isAdmin(user)?<Summary setError={setError}/>:page==="payments"?<Payments user={user} setError={setError} reloadUser={load}/>:page==="recipients"&&isAdmin(user)?<Recipients setError={setError}/>:isAdmin(user)?<AdminDashboard/>:<TenantDashboard user={user}/>} 
 </main></div>
}

function Login({onDone}){
 const [mode,setMode]=useState("login"),[resetSent,setResetSent]=useState(false),[identifier,setIdentifier]=useState(""),[error,setError]=useState("");
 async function submit(e){e.preventDefault();setError("");try{const f=new FormData(e.currentTarget);let r;
  if(mode==="register")r=await fetch(API+"/api/auth/register",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(Object.fromEntries(f))});
  else if(mode==="forgot"){
   const value=String(f.get("identifier")||identifier).trim();
   r=await fetch(API+(resetSent?"/api/auth/reset-password":"/api/auth/forgot-password"),{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(resetSent?{identifier:value,code:f.get("code"),new_password:f.get("new_password")}:{identifier:value})});
   const d=await r.json();if(!r.ok)return setError(d.detail||"Could not reset password");
   if(!resetSent){setIdentifier(value);setResetSent(true);return}alert("Password changed. You can now sign in.");setMode("login");setResetSent(false);return
  }else{const body=new URLSearchParams();body.set("username",f.get("identifier"));body.set("password",f.get("password"));r=await fetch(API+"/api/auth/login",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},body})}
  const d=await r.json();if(!r.ok)return setError(d.detail||"Could not sign in");localStorage.setItem("token",d.access_token);localStorage.setItem(LAST_ACTIVITY,String(Date.now()));localStorage.setItem(LAST_REFRESH,String(Date.now()));onDone()}catch{setError("Could not connect to the website. Try again shortly.")}}
 const switchMode=value=>{setMode(value);setResetSent(false);setIdentifier("");setError("")};
 return <div className="login"><div className="login-card"><div className="brand"><Home/> Akshar Purushottam Chhatralay</div><h1>{mode==="register"?"Create tenant account":mode==="forgot"?"Reset password":"Sign in"}</h1><p>{mode==="register"?"Use the email saved by your administrator and the six-digit verification code.":mode==="forgot"?(resetSent?"Enter the six-digit code from your email and choose a new password.":"We will email a six-digit code to the address on your account."):"Use your email address or unique number."}</p>{error&&<div className="error">{error}</div>}<form onSubmit={submit}>{mode==="register"&&<Field name="full_name" label="Full name" autoComplete="name"/>}{mode==="register"?<Field name="email" label="Email" type="email" autoComplete="email"/>:<Field name="identifier" label="Email or unique number" defaultValue={identifier} readOnly={mode==="forgot"&&resetSent} autoComplete="username"/>}{mode==="login"&&<Field name="password" label="Password" type="password" autoComplete="current-password"/>}{mode==="register"&&<><Field name="password" label="Password" type="password" autoComplete="new-password"/><Field name="invite_code" label="Six-digit email code" inputMode="numeric" pattern="[0-9]{6}" maxLength="6" autoComplete="one-time-code"/></>}{mode==="forgot"&&resetSent&&<><Field name="code" label="Six-digit reset code" inputMode="numeric" pattern="[0-9]{6}" maxLength="6" autoComplete="one-time-code"/><Field name="new_password" label="New password (at least 12 characters)" type="password" minLength="12" autoComplete="new-password"/></>}<button className="primary">{mode==="register"?"Verify and create account":mode==="forgot"?(resetSent?"Change password":"Email reset code"):"Sign in"}</button></form><div className="login-links">{mode!=="login"&&<button className="link" onClick={()=>switchMode("login")}>Back to sign in</button>}{mode==="login"&&<><button className="link" onClick={()=>switchMode("register")}>Tenant? Create your account</button><button className="link" onClick={()=>switchMode("forgot")}>Forgot password?</button></>}</div></div></div>
}
const Field=({name,label,type="text",...p})=><label>{label}<input name={name} type={type} required {...p}/></label>;

function TenantDashboard({user}){
 const t=user.tenant;if(!t)return <Empty title="Your tenant profile is not linked" text="Ask the administrator to check the email on your resident record."/>;
 return <><div className="cards"><Card title="Outstanding balance" value={aud(t.balance)} tone={t.balance>0?"warn":"ok"}/><Card title="Monthly rent" value={aud(t.monthly_rent)}/><Card title="Room" value={t.room}/></div><section><h2>Your rent history</h2>{!t.charges.length?<Empty title="No rent charges yet" text="New charges will appear here."/>:<table><thead><tr><th>Due date</th><th>Charge</th><th>Paid</th><th>Balance</th></tr></thead><tbody>{t.charges.map(c=><tr key={c.id}><td>{c.due_date}</td><td>{aud(c.amount)}</td><td>{aud(c.paid)}</td><td className={c.balance>0?"due":""}>{aud(c.balance)}</td></tr>)}</tbody></table>}</section></>
}
function AdminDashboard(){
 const [d,setD]=useState(null),[message,setMessage]=useState("");
 const load=()=>fetch(API+"/api/admin/dashboard",{headers:auth()}).then(r=>r.json()).then(setD);
 async function chargeEveryone(e){e.preventDefault();const form=e.currentTarget;const due_date=new FormData(form).get("due_date");if(!confirm(`Create a rent charge for every active tenant due on ${due_date}? Each person's saved monthly rent will be used.`))return;setMessage("");try{const r=await fetch(API+"/api/admin/charges/all",{method:"POST",headers:{...auth(),"Content-Type":"application/json"},body:JSON.stringify({due_date})});const data=await r.json();if(!r.ok)throw Error(data.detail||"Could not create rent charges");setMessage(`${data.created} rent charges created. Email notices have been queued; check Render logs if an email does not arrive.`);form.reset();await load()}catch(e){setMessage(e.message)}}
 useEffect(()=>{void load()},[]);
 if(!d)return <div>Loading…</div>;
 return <><div className="cards"><Card title="Total active tenants" value={d.tenants.length}/><Card title="Tenants with outstanding rent" value={d.pending.length} tone="warn"/><Card title="Total outstanding" value={aud(d.total_outstanding)} tone="warn"/></div>{message&&<p role="status">{message}</p>}<section><h2>Charge all active tenants</h2><p className="muted">Choose a due date. Each tenant is charged their saved monthly rent and an email notice is queued.</p><form className="grid-form" onSubmit={chargeEveryone}><Field name="due_date" label="Rent due date" type="date"/><button className="primary">Create charges for everyone</button></form></section><details className="panel"><summary>View outstanding rent ({d.pending.length})</summary>{!d.pending.length?<p>No outstanding rent.</p>:<div className="table-scroll"><table><thead><tr><th>Tenant</th><th>Room</th><th>Outstanding</th></tr></thead><tbody>{d.pending.map(t=><tr key={t.id}><td>{t.name}</td><td>{t.room}</td><td className="due">{aud(t.balance)}</td></tr>)}</tbody></table></div>}</details><details className="panel"><summary>Charge one tenant</summary><ChargeForm tenants={d.tenants} reload={load}/></details></>
}

function ProfileDetails({profile,showPayments=false}){
 const p=profile;
 const fields=[["Name",p.full_name],["Role",p.account_role==="tenant_admin"?"Tenant and admin":p.account_role==="admin"?"Admin only":"Tenant"],["Unique number",p.unique_number],["Allocated seva",p.allocated_seva],["Email",p.email],["Mobile number",p.phone],["Date of birth",p.date_of_birth],["Parent’s mobile",p.parent_phone],["Home address",p.current_address],["Arrival date",p.move_in_date],["University",p.university_name],["Course",p.course_name],["Graduation month",p.graduation_month],["Referee name",p.reference_name],["Referee contact",p.reference_phone],["Referee location",p.referee_location],["Account",p.registered?"Registered":"Not registered"]];
 return <><TenantPhoto id={p.id} hasPhoto={p.has_photo} version={p.photo_version}/><dl className="tenant-details">{fields.map(([label,value])=><ReactFragment key={label} label={label} value={value}/>)}</dl>{p.account_role!=="admin"&&<><h3>Rent</h3><p>Monthly rent: {aud(p.monthly_rent)} · Room: {p.room||"—"} · Bond: {aud(p.bond_amount)}</p><h3>Rent charges</h3>{!p.charges.length?<p>No rent charges yet.</p>:<table><thead><tr><th>Due date</th><th>Amount</th><th>Paid</th><th>Note</th></tr></thead><tbody>{p.charges.map(c=><tr key={c.id}><td>{c.due_date}</td><td>{aud(c.amount)}</td><td>{aud(c.paid)}</td><td>{c.note}</td></tr>)}</tbody></table>}{showPayments&&<><h3>Payment submissions (last 365 days)</h3>{!p.payments.length?<p>No recent payments submitted.</p>:<table><thead><tr><th>Date</th><th>Amount</th><th>Bank reference</th><th>Status</th></tr></thead><tbody>{p.payments.map(payment=><tr key={payment.id}><td>{payment.payment_date}</td><td>{aud(payment.amount)}</td><td>{payment.bank_reference}</td><td>{payment.state}</td></tr>)}</tbody></table>}</>}</>}</>
}
function TenantPhoto({id,hasPhoto,version}){
 const [src,setSrc]=useState(null);
 useEffect(()=>{if(!hasPhoto)return;let current=true;let url;fetch(API+`/api/tenants/${id}/photo`,{headers:auth()}).then(r=>{if(!r.ok)throw Error("Photo unavailable");return r.blob()}).then(blob=>{url=URL.createObjectURL(blob);if(current)setSrc(url);else URL.revokeObjectURL(url)}).catch(()=>{});return()=>{current=false;if(url)URL.revokeObjectURL(url)}},[id,hasPhoto,version]);
 return hasPhoto?<img className="profile-photo" src={src||undefined} alt="Tenant profile"/>:null;
}
function ReactFragment({label,value}){return <><dt>{label}</dt><dd>{value||"—"}</dd></>}

function Tenants({setError}){
 const [items,setItems]=useState(null),[selected,setSelected]=useState(null);
 const [loading,setLoading]=useState(false),[query,setQuery]=useState(""),[showArchived,setShowArchived]=useState(false);
 const visible=items?.filter(t=>(showArchived||t.is_active)&&`${t.name} ${t.room} ${t.email} ${t.unique_number} ${t.allocated_seva}`.toLowerCase().includes(query.toLowerCase()))||[];
 const load=async()=>{const r=await fetch(API+"/api/admin/tenants",{headers:auth()});const data=await r.json();if(!r.ok)throw Error(data.detail||"Could not load tenants");setItems(data)};
 useEffect(()=>{void load().catch(e=>setError(e.message))},[setError]);
 async function openTenant(id){setLoading(true);setError("");try{const r=await fetch(API+`/api/admin/tenants/${id}`,{headers:auth()});const data=await r.json();if(!r.ok)throw Error(data.detail||"Could not load tenant details");setSelected({...data,photo_version:Date.now()})}catch(e){setError(e.message)}finally{setLoading(false)}}
 async function updateStatus(action){if(!selected)return;const active=action==="archive";if(active&&!confirm(`Remove ${selected.full_name} from active tenants? Their payment records will be kept.`))return;
  setLoading(true);setError("");try{const r=await fetch(API+`/api/admin/tenants/${selected.id}/${action}`,{method:"POST",headers:auth()});const data=await r.json();if(!r.ok)throw Error(data.detail||"Could not update tenant");setSelected(null);await load()}catch(e){setError(e.message)}finally{setLoading(false)}}
 async function resend(t){try{const r=await fetch(API+`/api/admin/tenants/${t.id}/invite`,{method:"POST",headers:auth()});const data=await r.json();if(!r.ok)throw Error(data.detail||"Could not send code");alert(`Verification code queued for ${t.email}. Check delivery in Render logs.`)}catch(e){setError(e.message)}}
 async function download(){setError("");try{const r=await fetch(API+"/api/admin/tenants/report.csv",{headers:auth()});if(!r.ok)throw Error("Could not download tenant report");const url=URL.createObjectURL(await r.blob());const link=document.createElement("a");link.href=url;link.download="apc-tenants-all.csv";link.click();setTimeout(()=>URL.revokeObjectURL(url),60000)}catch(e){setError(e.message)}}
 async function emailTenant(e){e.preventDefault();const form=e.currentTarget;const f=new FormData(form);try{const r=await fetch(API+`/api/admin/tenants/${selected.id}/email`,{method:"POST",headers:{...auth(),"Content-Type":"application/json"},body:JSON.stringify({subject:f.get("subject"),message:f.get("message")})});const d=await r.json();if(!r.ok)throw Error(d.detail||"Could not send email");form.reset();alert("Email queued. Check Resend for delivery status.")}catch(e){setError(e.message)}}
 async function editTenant(e){e.preventDefault();const f=new FormData(e.currentTarget);const body=Object.fromEntries(f);body.date_of_birth=body.date_of_birth||null;try{const r=await fetch(API+`/api/admin/tenants/${selected.id}`,{method:"PATCH",headers:{...auth(),"Content-Type":"application/json"},body:JSON.stringify(body)});const d=await r.json();if(!r.ok)throw Error(d.detail||"Could not save details");setSelected(d);await load();alert("Tenant details updated") }catch(e){setError(e.message)}}
 async function correctEmail(e){e.preventDefault();const email=String(new FormData(e.currentTarget).get("email")).trim();if(!confirm(`Send a new registration code to ${email}? The previous code will stop working.`))return;setError("");try{const r=await fetch(API+`/api/admin/tenants/${selected.id}/login-email`,{method:"PATCH",headers:{...auth(),"Content-Type":"application/json"},body:JSON.stringify({email})});const d=await r.json();if(!r.ok)throw Error(d.detail||"Could not change email");await openTenant(selected.id);await load();alert(`Email updated to ${d.email}. New verification code queued; check Resend for delivery.`)}catch(error){setError(error.message)}}
 async function changePhoto(e){e.preventDefault();const form=e.currentTarget;const photo=new FormData(form).get("photo");if(!photo||!photo.size)return;setError("");try{const body=new FormData();body.append("photo",photo);const r=await fetch(API+`/api/admin/tenants/${selected.id}/photo`,{method:"POST",headers:auth(),body});const d=await r.json();if(!r.ok)throw Error(d.detail||"Could not upload photo");form.reset();await openTenant(selected.id)}catch(e){setError(e.message)}}
 async function deletePhoto(){if(!confirm("Remove this tenant's photo?"))return;const r=await fetch(API+`/api/admin/tenants/${selected.id}/photo`,{method:"DELETE",headers:auth()});if(r.ok)await openTenant(selected.id);else setError("Could not remove photo")}
 const outstanding=selected?.charges.reduce((total,c)=>total+Math.max(0,c.amount-c.paid),0)||0;
 const pending=selected?.payments.some(p=>p.state==="pending")||false;
 if(selected)return <section className="tenant-profile"><button className="link" onClick={()=>setSelected(null)}>← All tenants</button><h2>{selected.full_name}</h2><p className="muted">{selected.is_active?"Active tenant":"Archived tenant"}</p><ProfileDetails profile={selected} showPayments/>
  <details className="panel"><summary>{selected.has_photo?"Change profile photo":"Add profile photo"}</summary><form className="grid-form" onSubmit={changePhoto}><label>Photo (JPG, PNG or WebP, max 1 MB)<input name="photo" type="file" accept="image/jpeg,image/png,image/webp" required/></label><button className="primary">Upload photo</button></form>{selected.has_photo&&<button className="link" onClick={deletePhoto}>Remove photo</button>}</details>
  <details className="panel"><summary>Edit personal details</summary><form className="grid-form" onSubmit={editTenant}><Field name="full_name" label="Name" defaultValue={selected.full_name}/><Field name="allocated_seva" label="Allocated seva" required={false} defaultValue={selected.allocated_seva||""}/><Field name="phone" label="Mobile number" defaultValue={selected.phone||""}/><Field name="date_of_birth" label="Date of birth" type="date" required={false} defaultValue={selected.date_of_birth||""}/><Field name="parent_phone" label="Parent’s mobile" required={false} defaultValue={selected.parent_phone||""}/><Field name="current_address" label="Home address" defaultValue={selected.current_address||""}/><Field name="move_in_date" label="Arrival date" type="date" defaultValue={selected.move_in_date}/><Field name="university_name" label="University" required={false} defaultValue={selected.university_name||""}/><Field name="course_name" label="Course" required={false} defaultValue={selected.course_name||""}/><Field name="graduation_month" label="Graduation month" type="month" required={false} defaultValue={selected.graduation_month||""}/><Field name="reference_name" label="Referee name" required={false} defaultValue={selected.reference_name||""}/><Field name="reference_phone" label="Referee contact" required={false} defaultValue={selected.reference_phone||""}/><Field name="referee_location" label="Referee location" required={false} defaultValue={selected.referee_location||""}/><button className="primary">Save changes</button></form></details>
  {!selected.registered&&selected.is_active&&<details className="panel"><summary>Correct email address</summary><p className="muted">The tenant has not registered yet. Saving the correct email cancels the previous code and queues a new six-digit code.</p><form className="grid-form" onSubmit={correctEmail}><Field name="email" label="Correct email" type="email" defaultValue={selected.email}/><button className="primary">Update email and send code</button></form></details>}
  <details className="panel"><summary>Send personal email</summary><form className="grid-form" onSubmit={emailTenant}><p className="muted">Sent privately to {selected.email}.</p><Field name="subject" label="Subject" maxLength="180"/><label className="full-width">Message<textarea name="message" rows="6" maxLength="3000" required/></label><button className="primary">Send to this tenant</button></form></details>
  <div className="profile-actions">{selected.is_active?<><button className="danger" disabled={loading||outstanding>0||pending} onClick={()=>updateStatus("archive")}>Remove tenant</button>{outstanding>0&&<p>Removal is available after all rent is paid. Outstanding: {aud(outstanding)}.</p>}{pending&&<p>Review pending payment submissions before removal.</p>}</>:<button className="primary" disabled={loading} onClick={()=>updateStatus("restore")}>Restore tenant</button>}</div>
 </section>;
 return <section><h2>Tenants</h2><p className="muted">Select a name to see its saved details and payment history. The CSV includes active and archived tenants.</p><button className="primary" onClick={download}>Download all tenants (CSV)</button><div className="tenant-filters"><label className="tenant-search">Search tenants<input type="search" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Name, room or email"/></label><label className="checkbox"><input type="checkbox" checked={showArchived} onChange={e=>setShowArchived(e.target.checked)}/> Show archived</label></div>
 {items===null?<p>Loading tenants…</p>:!items.length?<p>No tenants added yet.</p>:!visible.length?<p>No matching tenants.</p>:<div className="table-scroll"><table><thead><tr><th>Name</th><th>Unique no.</th><th>Seva</th><th>Room</th><th>Email</th><th>Status</th><th>Registration</th></tr></thead><tbody>{visible.map(t=><tr key={t.id}><td><button className="tenant-name" onClick={()=>openTenant(t.id)}>{t.name}</button></td><td>{t.unique_number}</td><td>{t.allocated_seva||"—"}</td><td>{t.room}</td><td>{t.email}</td><td>{t.is_active?"Active":"Archived"}</td><td>{t.registered?"Registered":t.is_active?<button className="link" onClick={()=>resend(t)}>Send verification code</button>:"Not registered"}</td></tr>)}</tbody></table></div>}{loading&&<p>Loading tenant details…</p>}</section>
}

function Summary({setError}){
 const [year,setYear]=useState(new Date().getFullYear()),[busy,setBusy]=useState(false);
 const years=Array.from({length:11},(_,i)=>new Date().getFullYear()+1-i);
 async function download(){setBusy(true);setError("");try{const r=await fetch(API+`/api/admin/summary.pdf?year=${year}`,{headers:auth()});if(!r.ok){const d=await r.json();throw Error(d.detail||"Could not create summary")};const url=URL.createObjectURL(await r.blob());const link=document.createElement("a");link.href=url;link.download=`chhatralay-summary-${year}.pdf`;link.click();setTimeout(()=>URL.revokeObjectURL(url),60000)}catch(e){setError(e.message)}finally{setBusy(false)}}
 return <section><h2>Chhatralay summary</h2><p className="muted">Download a live PDF with active resident details, allocated seva, yearly rent collected, outstanding rent, pending reviews and upcoming activities. Admin-only profiles are excluded. The PDF is generated when you click and is not stored in the database.</p><label className="year-picker">Calendar year<select value={year} onChange={e=>setYear(Number(e.target.value))}>{years.map(y=><option key={y}>{y}</option>)}</select></label><button className="primary" disabled={busy} onClick={download}>{busy?"Creating PDF…":"Download summary PDF"}</button></section>
}

function Collections({setError}){
 const [year,setYear]=useState(new Date().getFullYear()),[data,setData]=useState(null);
 useEffect(()=>{let active=true;setData(null);fetch(API+`/api/admin/collections?year=${year}`,{headers:auth()}).then(async r=>{const body=await r.json();if(!r.ok)throw Error(body.detail||"Could not load collections");if(active)setData(body)}).catch(e=>setError(e.message));return()=>{active=false}},[year,setError]);
 const years=Array.from({length:11},(_,i)=>new Date().getFullYear()+1-i);
 return <><section><h2>Rent collected by tenant</h2><label className="year-picker">Year (1 January to 1 January)<select value={year} onChange={e=>setYear(Number(e.target.value))}>{years.map(y=><option key={y} value={y}>{y} — {y+1}</option>)}</select></label><p className="muted">For {year}, this report includes approved tenant submissions and dated manual payments from 1 January {year} through 31 December {year}. Pending or rejected submissions are excluded.</p>{!data?<p>Loading collections…</p>:<><div className="cards"><Card title="Total collected" value={aud(data.total)} tone="ok"/><Card title="Tenants in report" value={data.tenants.length}/></div><div className="table-scroll"><table><thead><tr><th>Tenant</th><th>Room</th><th>Collected</th></tr></thead><tbody>{data.tenants.map(t=><tr key={t.tenant_id}><td>{t.name}{!t.active&&" (archived)"}</td><td>{t.room}</td><td>{aud(t.collected)}</td></tr>)}</tbody></table></div>{data.historical_undated>0&&<p className="muted">{aud(data.historical_undated)} in older manually recorded payments has no payment date in the original app, so it cannot be assigned to a specific year.</p>}</>}</section></>
}

function MyDetails({setError}){
 const [profile,setProfile]=useState(null);
 useEffect(()=>{let active=true;fetch(API+"/api/me/profile",{headers:auth()}).then(async r=>{const data=await r.json();if(!r.ok)throw Error(data.detail||"Could not load your details");if(active)setProfile(data)}).catch(e=>setError(e.message));return()=>{active=false}},[setError]);
 return <section><h2>My details</h2>{profile?<><p className="muted">These details were saved by your housing administrator. Ask them if anything needs correcting.</p><div className="cards"><Card title="My outstanding rent" value={aud(profile.charges.reduce((sum,c)=>sum+Math.max(0,c.amount-c.paid),0))}/></div><ProfileDetails profile={profile} showPayments/></>:<p>Loading your details…</p>}</section>
}

function ChargeForm({tenants,reload}){async function submit(e){e.preventDefault();const form=e.currentTarget;const f=new FormData(form);const r=await fetch(API+"/api/admin/charges",{method:"POST",headers:{...auth(),"Content-Type":"application/json"},body:JSON.stringify({tenant_id:+f.get("tenant_id"),due_date:f.get("due_date"),amount:+f.get("amount"),note:f.get("note")})});if(r.ok){form.reset();reload()}}
 return <section><h2>Add rent charge</h2><form className="grid-form" onSubmit={submit}><label>Tenant<select name="tenant_id" required>{tenants.map(t=><option value={t.id} key={t.id}>{t.name} — {t.room}</option>)}</select></label><Field name="due_date" label="Due date" type="date"/><Field name="amount" label="Amount (AUD)" type="number" step="0.01"/><Field name="note" label="Note"/><button className="primary">Add charge</button></form></section>}

function AddTenant({setError}){
 const [role,setRole]=useState("tenant");
 async function submit(e){
  e.preventDefault();const form=e.currentTarget;const data=new FormData(form);
  const photo=data.get("photo");data.delete("photo");
  if(photo?.size>1024*1024)return setError("Photo must be smaller than 1 MB");
  const body=Object.fromEntries(data);body.monthly_rent=Number(body.monthly_rent||0);body.date_of_birth=body.date_of_birth||null;
  setError("");try{
   const r=await fetch(API+"/api/admin/tenants",{method:"POST",headers:{...auth(),"Content-Type":"application/json"},body:JSON.stringify(body)});
   const result=await r.json();if(!r.ok)throw Error(result.detail||"Could not add profile");
   if(photo?.size){const upload=new FormData();upload.append("photo",photo);const uploaded=await fetch(API+`/api/admin/tenants/${result.id}/photo`,{method:"POST",headers:auth(),body:upload});if(!uploaded.ok){const error=await uploaded.json();throw Error("Profile saved, but photo upload failed: "+(error.detail||"Try adding it from Tenants"))}}
   form.reset();setRole("tenant");alert("Profile created. A six-digit registration code has been queued for email.")
  }catch(error){setError(error.message)}
 }
 return <section><h2>Add person</h2><p className="muted">Choose access before creating an account. Admin only cannot pay rent; tenant and admin can use both areas. Email is required for login.</p><form className="grid-form" onSubmit={submit}>
 <label>Account role<select name="account_role" value={role} onChange={e=>setRole(e.target.value)}><option value="tenant">Tenant only</option><option value="admin">Admin only</option><option value="tenant_admin">Tenant and admin</option></select></label>
 <Field name="full_name" label="Name"/><Field name="unique_number" label="Unique number" pattern="[A-Za-z0-9-]{3,50}"/><Field name="allocated_seva" label="Allocated seva" required={false}/><Field name="email" label="Email for login" type="email"/><Field name="phone" label="Mobile number" required={false}/><Field name="date_of_birth" label="Date of birth" type="date" required={false}/><Field name="parent_phone" label="Parent’s mobile" required={false}/><Field name="current_address" label="Home address" required={false}/><Field name="move_in_date" label="Arrival date" type="date"/><Field name="university_name" label="University" required={false}/><Field name="course_name" label="Course name" required={false}/><Field name="graduation_month" label="Graduation month" type="month" required={false}/><Field name="reference_name" label="Referee name" required={false}/><Field name="reference_phone" label="Referee contact" required={false}/><Field name="referee_location" label="Referee location" required={false}/>
 {role!=="admin"&&<Field name="monthly_rent" label="Monthly rent (AUD)" type="number" min="0.01" step="0.01"/>}
 <label>Profile photo (optional, max 1 MB)<input name="photo" type="file" accept="image/jpeg,image/png,image/webp"/></label><button className="primary">Save profile</button></form></section>
}

function Activities({user,setError}){
 const [items,setItems]=useState([]);
 const load=async()=>{try{const r=await fetch(API+"/api/activities",{headers:auth()});if(!r.ok)throw Error("Could not load activities");setItems(await r.json())}catch(e){setError(e.message)}};
 useEffect(()=>{void load()},[]);
 async function add(e){e.preventDefault();const form=e.currentTarget;const f=new FormData(form);const body={title:f.get("title"),description:f.get("description"),activity_date:f.get("activity_date"),poll_question:f.get("poll_question")||null,options:[f.get("option1"),f.get("option2"),f.get("option3")].filter(Boolean)};try{const r=await fetch(API+"/api/admin/activities",{method:"POST",headers:{...auth(),"Content-Type":"application/json"},body:JSON.stringify(body)});if(!r.ok)throw Error((await r.json()).detail||"Could not publish activity");form.reset();await load()}catch(error){setError(error.message)}}
 async function vote(poll,option){const r=await fetch(API+`/api/polls/${poll}/vote`,{method:"POST",headers:{...auth(),"Content-Type":"application/json"},body:JSON.stringify({option_id:option})});const d=await r.json();if(!r.ok)setError(d.detail);else await load()}
 const upcoming=items.filter(a=>!a.completed),past=items.filter(a=>a.completed);
 const tenantVotes=participation=><details className="vote-details"><summary>View tenant votes</summary><div className="table-scroll"><table><thead><tr><th>Tenant</th><th>Choice</th></tr></thead><tbody>{participation?.map(v=><tr key={v.tenant_id}><td>{v.name}{!v.active&&" (archived)"}</td><td>{v.choice||"Not voted"}</td></tr>)}</tbody></table></div></details>;
 return <>
  {isAdmin(user)&&<section><h2>Post activity & poll</h2><form className="grid-form" onSubmit={add}><Field name="title" label="Activity title"/><Field name="activity_date" label="Date" type="date"/><Field name="description" label="Description"/><Field name="poll_question" label="Poll question (optional)"/><Field name="option1" label="Option 1"/><Field name="option2" label="Option 2"/><Field name="option3" label="Option 3 (optional)"/><button className="primary">Publish activity</button></form></section>}
  <section><h2>Upcoming activities</h2>{!upcoming.length?<p className="muted">No upcoming activities.</p>:<div className="activity-list">{upcoming.map(a=><article key={a.id}><div className="date">{a.date}</div><h3>{a.title}</h3><p>{a.description}</p>{a.poll&&<div className="poll"><strong>{a.poll.question}</strong>{a.poll.options.map(o=><button key={o.id} disabled={!isTenant(user)||!!a.poll.voted_option_id} onClick={()=>vote(a.poll.id,o.id)} className={a.poll.voted_option_id===o.id?"chosen":""}>{o.label}{isAdmin(user)&&` — ${o.votes} votes`}{a.poll.voted_option_id===o.id&&" ✓"}</button>)}{isAdmin(user)&&tenantVotes(a.poll.participation)}</div>}</article>)}</div>}</section>
  <section><h2>{isAdmin(user)?"Past activity summaries":"My past votes"}</h2>{!past.length?<p className="muted">{isAdmin(user)?"No completed activities yet.":"No past votes to show."}</p>:<div className="activity-list past">{past.map(a=><article key={a.id}><div className="date">Activity: {a.date}</div><h3>{a.title}</h3>{isAdmin(user)?<>{a.poll?<><p className="history-meta">{a.poll.total_votes} vote{a.poll.total_votes===1?"":"s"}{a.poll.question&&` · ${a.poll.question}`}</p><div className="vote-summary">{a.poll.summary.map((o,i)=><span key={i}>{o.label}: <strong>{o.votes}</strong></span>)}</div>{tenantVotes(a.poll.participation)}</>:<p className="history-meta">No poll for this activity.</p>}</>:<p className="history-meta">You voted <strong>{a.my_vote.choice}</strong> on {a.my_vote.submitted_on}.</p>}</article>)}</div>}</section>
 </>
}

function Payments({user,setError,reloadUser}){
 const [items,setItems]=useState([]),[busy,setBusy]=useState(false);
 const [mode,setMode]=useState(user.role==="tenant_admin"?"tenant":isAdmin(user)?"admin":"tenant");
 const endpoint=mode==="admin"?"/api/admin/payments":"/api/payments";
 const load=async()=>{try{const r=await fetch(API+endpoint,{headers:auth()});if(!r.ok)throw Error("Could not load payments");setItems(await r.json())}catch(e){setError(e.message)}};
 useEffect(()=>{void load()},[endpoint]);
 async function submit(e){e.preventDefault();const form=e.currentTarget;const body=new FormData(form);setBusy(true);setError("");try{
  const r=await fetch(API+"/api/payments",{method:"POST",headers:auth(),body});const data=await r.json();if(!r.ok)throw Error(data.detail||"Could not submit payment");form.reset();await load();
 }catch(e){setError(e.message)}finally{setBusy(false)}}
 async function review(p,decision){const note=decision==="rejected"?prompt("Reason for rejection (shown to tenant):"):"";if(note===null)return;setBusy(true);setError("");try{
  const r=await fetch(API+`/api/admin/payments/${p.id}/review`,{method:"POST",headers:{...auth(),"Content-Type":"application/json"},body:JSON.stringify({decision,note})});const data=await r.json();if(!r.ok)throw Error(data.detail||"Could not review payment");await load();await reloadUser();
 }catch(e){setError(e.message)}finally{setBusy(false)}}
 return <>{user.role==="tenant_admin"&&<div className="actions payment-tabs"><button onClick={()=>setMode("tenant")} aria-pressed={mode==="tenant"}>My payments</button><button onClick={()=>setMode("admin")} aria-pressed={mode==="admin"}>Review all payments</button></div>}{mode==="tenant"&&<section><h2>Submit a rent payment</h2><p className="muted">Your unique number is {user.unique_number}. Your balance changes after the admin verifies the transfer.</p><form className="grid-form" onSubmit={submit}><Field name="amount" label="Amount paid (AUD)" type="number" min="0.01" step="0.01"/><Field name="payment_date" label="Payment date" type="date"/><Field name="bank_reference" label="Bank transaction reference" maxLength="120"/><Field name="bank_details" label="Bank transfer details (optional; no account password)" required={false} maxLength="300"/><button className="primary" disabled={busy}>Submit for review</button></form></section>}
 <section><h2>{mode==="admin"?"Payment submissions":"My payment submissions"}</h2>{!items.length?<p className="muted">No payments submitted yet.</p>:<div className="table-scroll"><table><thead><tr>{mode==="admin"&&<th>Tenant</th>}<th>Amount</th><th>Date</th><th>Bank reference</th><th>Details</th><th>Status</th><th>Action</th></tr></thead><tbody>{items.map(p=><tr key={p.id}>{mode==="admin"&&<td>{p.tenant_name} (#{p.tenant_id})</td>}<td>{aud(p.amount)}</td><td>{p.payment_date}</td><td>{p.bank_reference}</td><td>{p.bank_details}</td><td>{p.state}{p.review_note&&<small> — {p.review_note}</small>}</td><td>{mode==="admin"&&p.state==="pending"?<div className="actions"><button disabled={busy} onClick={()=>review(p,"approved")}>Approve</button><button disabled={busy} onClick={()=>review(p,"rejected")}>Reject</button></div>:"—"}</td></tr>)}</tbody></table></div>}</section></>
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
