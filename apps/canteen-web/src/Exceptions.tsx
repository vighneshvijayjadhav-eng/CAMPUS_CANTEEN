import { useEffect, useState } from 'react'
import { api } from './api'
type Exception = {order_id:string;reason:string;contact_note:string|null;created_at:string}
export function Exceptions(){
  const [rows,setRows]=useState<Exception[]>([]);const [error,setError]=useState('')
  async function load(){try{setRows(await api<Exception[]>('/staff/exceptions'))}catch(e){setError((e as Error).message)}}
  useEffect(()=>{void load()},[])
  async function contact(order:string,event:React.FormEvent<HTMLFormElement>){event.preventDefault();const note=new FormData(event.currentTarget).get('contact_note');try{await api(`/staff/exceptions/${order}/contact`,'POST',{contact_note:note});await load()}catch(e){setError((e as Error).message)}}
  return <><p className="eyebrow">CANTEEN ADMINISTRATION</p><h1>Handover exceptions</h1><p className="warning">Partial collection cannot be undone automatically. Contact the student and record the discussion. Financial adjustments remain disabled until the partial-refund policy is approved.</p>{error&&<p role="alert" className="error">{error}</p>}{rows.map(row=><article className="card" key={row.order_id}><h2>Order {row.order_id.slice(0,8)}</h2><p>{row.reason.replaceAll('_',' ')}</p><form onSubmit={event=>contact(row.order_id,event)}><label>Contact note<input name="contact_note" defaultValue={row.contact_note ?? ''} required maxLength={2000}/></label><button>Record discussion</button></form><small>This does not cancel items or issue a refund.</small></article>)}{!rows.length&&<div className="card empty">No handover exceptions recorded.</div>}</>
}
