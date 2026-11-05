import React, { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { api, type Identity } from './api'
import { Orders } from './Orders'
import { Menu } from './Menu'
import { Stations } from './Stations'
import { Exceptions } from './Exceptions'
import { Sessions } from './Sessions'
import { Reviews } from './Reviews'
import './style.css'

function App(){
  const [identity,setIdentity]=useState<Identity|null>(null); const [page,setPage]=useState('Orders')
  const [error,setError]=useState(''); const [busy,setBusy]=useState(true)
  useEffect(()=>{api<Identity>('/staff/me').then(setIdentity).catch(()=>{}).finally(()=>setBusy(false))},[])
  async function login(event:React.FormEvent<HTMLFormElement>){event.preventDefault();setBusy(true);setError('');const data=new FormData(event.currentTarget)
    try{await api('/auth/staff/login','POST',Object.fromEntries(data));setIdentity(await api<Identity>('/staff/me'))}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
  async function logout(){try{await api('/auth/logout','POST');setIdentity(null);setPage('Orders')}catch(e){setError((e as Error).message)}}
  if(!identity)return <main className="login"><section><div className="brand"><span>AISSMS</span><strong>Campus Canteen</strong></div><h1>Good Food.<br/>A Better Campus.</h1><p>Sign in to your canteen or preparation station.</p><form onSubmit={login}><label>Username<input name="username" autoComplete="username" required/></label><label>Password<input name="password" type="password" autoComplete="current-password" required/></label><label>Device name<input name="device_name" placeholder="e.g. Juice counter tablet" required maxLength={120}/></label>{error&&<p className="error" role="alert">{error}</p>}<button disabled={busy}>{busy?'Connecting…':'Sign in'}</button></form><small>Provisioned staff accounts only. Contact your canteen administrator for access.</small></section><aside><p>One order.<br/>Every counter connected.</p><span>Development build · Live payments are not enabled.</span></aside></main>
  return <div className="shell"><aside className="sidebar"><div className="brand"><span>AISSMS</span><strong>Campus Canteen</strong></div><p>{identity.canteen}</p><nav>{['Orders',...(identity.role==='admin'?['Menu','Stations','Exceptions','Reviews']:[]),'Devices'].map(tab=><button className={page===tab?'selected':''} key={tab} onClick={()=>setPage(tab)}>{tab}</button>)}</nav><button onClick={logout}>Sign out</button><small>{identity.role==='admin'?'Canteen administrator':'Station operator'}</small></aside><main className="workspace"><div className="notice">Development build · Payments and student ordering are not enabled.</div>{error&&<p className="error" role="alert">{error}</p>}{page==='Orders'?<Orders/>:page==='Menu'?<Menu/>:page==='Stations'?<Stations/>:page==='Exceptions'?<Exceptions/>:page==='Reviews'?<Reviews/>:<Sessions/>}</main></div>
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>)
