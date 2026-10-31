import { useEffect, useRef, useState } from 'react'
import { api, type Line, type Order } from './api'

function Handover({line, order, updated}: {line: Line; order: string; updated: () => void}) {
  const [quantity, setQuantity] = useState(1)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [requestId] = useState(() => crypto.randomUUID())
  async function confirm() {
    if (!window.confirm(`Confirm you handed over ${quantity} × ${line.name}?`)) return
    setBusy(true); setError('')
    try {
      await api(`/staff/orders/${order}/lines/${line.id}/confirm`, 'POST', {quantity, expected_fulfilled: line.fulfilled, request_id: requestId})
      updated()
    } catch (e) { setError((e as Error).message + '. Refresh the order before changing this request.') }
    finally { setBusy(false) }
  }
  return <div className="handover"><div><strong>{line.name}</strong><small>{line.variant} · {line.station}</small><span>{line.fulfilled} of {line.quantity} collected</span></div>
    {line.remaining > 0 ? <div className="actions"><label>Handed over<input aria-label={`Quantity handed over: ${line.name}`} type="number" min="1" max={line.remaining} value={quantity} onChange={e=>setQuantity(Number(e.target.value))}/></label><button disabled={busy || quantity < 1 || quantity > line.remaining || !Number.isInteger(quantity)} onClick={confirm}>{busy ? 'Saving…' : 'Confirm handover'}</button></div> : <span className="positive">Collected</span>}
    {error && <p role="alert" className="error">{error}</p>}</div>
}

function OrderCard({order, updated}: {order: Order; updated:()=>void}) {
  return <article className="card"><header><h3>Order {order.id.slice(0,8)}</h3><span className="badge">{order.state.replaceAll('_',' ')}</span></header>
    {order.exception_status && <p className="warning">Cancellation after handover requires staff review. No refund has been initiated.</p>}
    {order.lines.map(line=><Handover key={`${line.id}:${line.fulfilled}`} line={line} order={order.id} updated={updated}/>)}</article>
}

export function Orders() {
  const [orders, setOrders] = useState<Order[]>([])
  const [preview, setPreview] = useState<Order | null>(null)
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [connected, setConnected] = useState(false)
  const [sound, setSound] = useState(false)
  const audio = useRef<AudioContext | null>(null)
  const soundEnabled = useRef(false)
  const lastEvent = useRef(0)
  const [lastUpdated, setLastUpdated] = useState('')
  async function load() {
    try { setOrders(await api<Order[]>('/staff/orders')); setError(''); setLastUpdated(new Date().toLocaleTimeString()) }
    catch(e) { setError((e as Error).message) }
  }
  function updated() { setPreview(null); void load() }
  useEffect(()=> {
    let active = true
    let events: EventSource | undefined
    let reconnect: ReturnType<typeof setTimeout> | undefined
    void load()
    const poll = setInterval(load, 5000)
    function connect() {
      if (!active) return
      events = new EventSource(`/api/v1/staff/events?after=${lastEvent.current}`, {withCredentials:true})
      events.onopen = ()=>setConnected(true)
      events.onmessage = event=> {
        const payload = JSON.parse(event.data)
        if (payload.id <= lastEvent.current) return
        lastEvent.current = payload.id
        setPreview(null); void load()
        if (payload.kind === 'PAID' && soundEnabled.current && audio.current) {
          const oscillator = audio.current.createOscillator(); const gain = audio.current.createGain()
          gain.gain.value = 0.05; oscillator.connect(gain); gain.connect(audio.current.destination)
          oscillator.start(); oscillator.stop(audio.current.currentTime + 0.15)
        }
      }
      const retry = ()=> { events?.close(); setConnected(false); reconnect = setTimeout(connect, 5000) }
      events.onerror = retry
      events.addEventListener('expired', ()=> { void api('/staff/me').finally(retry).catch(()=>{}) })
    }
    connect()
    return ()=> { active=false; events?.close(); clearInterval(poll); clearTimeout(reconnect) }
  },[])
  async function find(event: React.FormEvent) {
    event.preventDefault(); setError(''); setPreview(null)
    try { setPreview(await api<Order>('/staff/pickup/lookup','POST',{code})) }
    catch(e) { setError((e as Error).message) }
  }
  function toggleSound() {
    if (!audio.current) audio.current = new AudioContext()
    void audio.current.resume()
    soundEnabled.current = !sound; setSound(!sound)
  }
  return <><header className="page-title"><div><p className="eyebrow">COUNTER OPERATIONS</p><h1>Orders & pickup</h1><p>Confirm only the food you have handed over.</p></div><button className="secondary" onClick={toggleSound}>{sound ? 'Mute sound' : 'Enable sound'}</button></header>
    <p className="connection">{connected ? 'Live updates connected' : 'Polling every 5 seconds'} · Last refreshed {lastUpdated || '—'}</p>
    <form className="card pickup" onSubmit={find}><label htmlFor="pickup">Enter six-digit pickup code</label><div><input id="pickup" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} value={code} onChange={e=>setCode(e.target.value.replace(/\D/g,''))} placeholder="000000" required autoComplete="off"/><button>Find order</button></div><small>Looking up a code does not collect any items.</small></form>
    {error && <p className="error" role="alert">{error}</p>}
    {preview && <section><h2>Pickup preview</h2><OrderCard order={preview} updated={updated}/></section>}
    <h2>Active queue <span className="count">{orders.length}</span></h2>
    {orders.map(order=><OrderCard key={order.id} order={order} updated={updated}/>)}
    {!orders.length && !error && <div className="card empty">No paid orders are waiting at your counter.</div>}</>
}
