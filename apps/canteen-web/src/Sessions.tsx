import { useEffect, useState } from 'react'
import { api } from './api'
type Session={id:string;device:string;revoked:boolean;expires_at:string}
export function Sessions(){
  const [rows,setRows]=useState<Session[]>([]);const [error,setError]=useState('')
  async function load(){try{setRows(await api<Session[]>('/staff/sessions'))}catch(e){setError((e as Error).message)}}
  useEffect(()=>{void load()},[])
  async function revoke(id:string){if(!window.confirm('Sign this device out?'))return;try{await api(`/staff/sessions/${id}/revoke`,'POST');await load()}catch(e){setError((e as Error).message)}}
  return <><p className="eyebrow">ACCOUNT SECURITY</p><h1>Your signed-in devices</h1><p>Revoke a lost or shared device. Sessions have a fixed maximum lifetime and can be renewed by signing in.</p>{error&&<p role="alert" className="error">{error}</p>}{rows.map(row=><article className="card" key={row.id}><h2>{row.device}</h2><p>{row.revoked?'Revoked':`Expires ${new Date(row.expires_at).toLocaleString()}`}</p><button className="secondary" disabled={row.revoked} onClick={()=>revoke(row.id)}>Revoke device</button></article>)}</>
}
