import { useEffect, useState } from 'react'
import { api, type Station } from './api'

export function Stations(){
  const [stations,setStations]=useState<Station[]>([]);const [name,setName]=useState('');const [error,setError]=useState('')
  async function load(){try{setStations(await api<Station[]>('/staff/stations'))}catch(e){setError((e as Error).message)}}
  useEffect(()=>{void load()},[])
  async function add(e:React.FormEvent){e.preventDefault();try{await api('/staff/stations','POST',{name,active:true});setName('');await load()}catch(e){setError((e as Error).message)}}
  async function edit(station:Station,changes:Partial<Station>){try{await api(`/staff/stations/${station.id}`,'PATCH',{name:station.name,active:station.active,...changes});await load()}catch(e){setError((e as Error).message)}}
  return <><p className="eyebrow">CANTEEN SETTINGS</p><h1>Preparation stations</h1><p>Each station has its own provisioned account. Disabling a station blocks its staff access; admins can still hand over its outstanding items.</p>
    {error&&<p className="error" role="alert">{error}</p>}
    <form className="card inline" onSubmit={add}><label>New station name<input value={name} onChange={e=>setName(e.target.value)} required maxLength={80}/></label><button>Add station</button></form>
    {stations.map(s=><article className="card" key={s.id}><h2>{s.name}</h2><small>Provisioning ID: {s.id}</small><div className="actions"><button className="secondary" onClick={()=>{const updated=window.prompt('Station name',s.name);if(updated?.trim())void edit(s,{name:updated.trim()})}}>Rename</button><button className="secondary" onClick={()=>edit(s,{active:!s.active})}>{s.active?'Disable':'Enable'}</button></div></article>)}</>
}
