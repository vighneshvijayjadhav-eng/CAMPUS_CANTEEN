import { useEffect, useState } from 'react'
import { api, type Item, type Station, type Variant } from './api'

function VariantEditor({variant, itemId, stations, saved}: {variant:Variant; itemId:string; stations:Station[]; saved:()=>void}) {
  const [value,setValue]=useState(variant)
  const [error,setError]=useState('')
  const [busy,setBusy]=useState(false)
  async function save(e:React.FormEvent) {
    e.preventDefault(); setBusy(true); setError('')
    const {id,...body}=value
    try {await api(id ? `/staff/variants/${id}` : `/staff/menu/${itemId}/variants`,id ? 'PATCH' : 'POST',body); saved()}
    catch(e){setError((e as Error).message)} finally {setBusy(false)}
  }
  return <form className="variant" onSubmit={save}>
    <label>Size / variant<input value={value.label} onChange={e=>setValue({...value,label:e.target.value})} required/></label>
    <label>Price (paise)<input type="number" min="1" step="1" value={value.price_paise ?? ''} onChange={e=>setValue({...value,price_paise:e.target.value===''?null:Number(e.target.value)})} placeholder="Needs verification"/><small>100 paise = ₹1</small></label>
    <label>Preparation station<select value={value.station_id ?? ''} onChange={e=>setValue({...value,station_id:e.target.value || null})}><option value="">Not assigned</option>{stations.map(s=><option disabled={!s.active} key={s.id} value={s.id}>{s.name}{!s.active?' (disabled)':''}</option>)}</select></label>
    <label className="check"><input type="checkbox" checked={value.verified} onChange={e=>setValue({...value,verified:e.target.checked,available:false})}/>Price and size verified</label>
    <label className="check"><input type="checkbox" checked={value.available} disabled={!value.verified || !value.station_id || !value.price_paise} onChange={e=>setValue({...value,available:e.target.checked})}/>Available</label>
    <button disabled={busy}>{busy?'Saving…':'Save variant'}</button>{error&&<p className="error" role="alert">{error}</p>}</form>
}

function ItemEditor({item,saved}:{item?:Item;saved:()=>void}){
  const [name,setName]=useState(item?.name ?? '');const [category,setCategory]=useState(item?.category ?? '');const [error,setError]=useState('');const [busy,setBusy]=useState(false)
  async function save(e:React.FormEvent){e.preventDefault();setBusy(true);setError('');try{await api(item?`/staff/menu/${item.id}`:'/staff/menu',item?'PATCH':'POST',{name,category,archived:item?.archived ?? false});if(!item){setName('');setCategory('')}saved()}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
  return <form className="variant" onSubmit={save}><label>Item name<input value={name} onChange={e=>setName(e.target.value)} required maxLength={160}/></label><label>Display category<input value={category} onChange={e=>setCategory(e.target.value)} required maxLength={120}/></label><button disabled={busy}>{busy?'Saving…':item?'Save item details':'Create item'}</button>{error&&<p className="error" role="alert">{error}</p>}</form>
}

export function Menu(){
  const [items,setItems]=useState<Item[]>([]); const [stations,setStations]=useState<Station[]>([])
  const [search,setSearch]=useState(''); const [error,setError]=useState('')
  async function load(){try{const [menu,counters]=await Promise.all([api<Item[]>('/staff/menu'),api<Station[]>('/staff/stations')]);setItems(menu);setStations(counters)}catch(e){setError((e as Error).message)}}
  useEffect(()=>{void load()},[])
  async function archive(item:Item){try{await api(`/staff/menu/${item.id}`,'PATCH',{name:item.name,category:item.category,archived:!item.archived});await load()}catch(e){setError((e as Error).message)}}
  return <><p className="eyebrow">YOUR CANTEEN</p><h1>Menu & station mapping</h1><p>Verify prices and sizes against the counter menu. Categories do not determine preparation stations.</p>
    <details className="card"><summary>Add menu item</summary><ItemEditor saved={load}/></details>
    <label className="search">Search menu<input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Name or category"/></label>
    {error&&<p className="error" role="alert">{error}</p>}
    {items.filter(i=>`${i.name} ${i.category}`.toLowerCase().includes(search.toLowerCase())).map(item=><details className="card" key={item.id}><summary><strong>{item.name}</strong><span>{item.category} · {item.archived?'Archived':`${item.variants.length} variant(s)`}</span></summary>
      <small>{item.source_sheet ? `Source: ${item.source_sheet}, row ${item.source_row}`:'Staff-created item'}</small>
      <ItemEditor key={`${item.name}:${item.category}:${item.archived}`} item={item} saved={load}/>
      {item.variants.map(v=><VariantEditor key={JSON.stringify(v)} variant={v} itemId={item.id} stations={stations} saved={load}/>)}
      <details><summary>Add size / variant</summary><VariantEditor key={item.variants.length} itemId={item.id} variant={{id:'',label:'',price_paise:null,station_id:null,verified:false,available:false}} stations={stations} saved={load}/></details>
      <button className="secondary" onClick={()=>archive(item)}>{item.archived?'Restore item':'Archive item'}</button></details>)}</>
}
