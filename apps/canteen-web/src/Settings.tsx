import { useEffect, useState } from 'react'
import { api } from './api'

type Window = { weekday: number; opens: string; closes: string }
type CanteenSettings = {
  id: string; name: string; operating: boolean; accepting_orders: boolean
  closed_reason: string | null; timezone: string; hours: Window[]
}
type Merchant = { id: string; key_id: string; mode: string; display_name: string; active: boolean; activated_at: string | null; webhook_path: string }

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

export function Settings() {
  const [settings, setSettings] = useState<CanteenSettings | null>(null)
  const [hours, setHours] = useState<Record<number, Window | undefined>>({})
  const [merchants, setMerchants] = useState<Merchant[]>([])
  const [error, setError] = useState(''); const [saved, setSaved] = useState(''); const [busy, setBusy] = useState(false)

  function apply(data: CanteenSettings) {
    setSettings(data)
    setHours(Object.fromEntries(data.hours.map(w => [w.weekday, w])))
  }
  async function load() {
    try {
      apply(await api<CanteenSettings>('/staff/canteen'))
      setMerchants(await api<Merchant[]>('/staff/merchant'))
    } catch (e) { setError((e as Error).message) }
  }
  useEffect(() => { void load() }, [])

  async function save(body: object, message: string) {
    setBusy(true); setError(''); setSaved('')
    try { apply(await api<CanteenSettings>('/staff/canteen', 'PATCH', body)); setSaved(message) }
    catch (e) { setError((e as Error).message) }
    finally { setBusy(false) }
  }

  if (!settings) return <>{error ? <p role="alert" className="error">{error}</p> : <p>Loading…</p>}</>
  const windows = Object.values(hours).filter((w): w is Window => !!w)

  return <>
    <p className="eyebrow">CANTEEN ADMINISTRATION</p>
    <h1>Settings</h1>
    {error && <p role="alert" className="error">{error}</p>}
    {saved && <p role="status" className="notice">{saved}</p>}

    <article className="card">
      <h2>Online ordering</h2>
      <p>{settings.accepting_orders ? 'Students can order now.' : `Students cannot order now (${(settings.closed_reason ?? '').replaceAll('_', ' ').toLowerCase()}).`}</p>
      <button disabled={busy} className={settings.operating ? 'secondary' : ''}
        onClick={() => save({ operating: !settings.operating }, settings.operating ? 'Ordering paused.' : 'Ordering resumed.')}>
        {settings.operating ? 'Pause ordering' : 'Resume ordering'}
      </button>
      <small> Pausing stops new orders only. Paid orders stay in the queue.</small>
    </article>

    <article className="card">
      <h2>Opening hours ({settings.timezone})</h2>
      <p>Leave every day unchecked to rely on the switch above alone. Once any day is set, unchecked days are closed.</p>
      {DAYS.map((day, weekday) => {
        const window = hours[weekday]
        return <div key={day} style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', margin: '.4rem 0' }}>
          <label style={{ minWidth: 140 }}>
            <input type="checkbox" checked={!!window}
              onChange={e => setHours({ ...hours, [weekday]: e.target.checked ? { weekday, opens: '08:00', closes: '17:00' } : undefined })} /> {day}
          </label>
          {window && <>
            <label>Opens <input type="time" value={window.opens} onChange={e => setHours({ ...hours, [weekday]: { ...window, opens: e.target.value } })} /></label>
            <label>Closes <input type="time" value={window.closes === '24:00' ? '23:59' : window.closes} onChange={e => setHours({ ...hours, [weekday]: { ...window, closes: e.target.value } })} /></label>
          </>}
        </div>
      })}
      <button disabled={busy} onClick={() => save({ hours: windows }, 'Opening hours saved.')}>Save hours</button>
    </article>

    <article className="card">
      <h2>Payment account (Razorpay)</h2>
      {merchants.length === 0
        ? <p>No merchant account is set up yet. The platform owner registers it on the server; secrets are never entered here.</p>
        : <table><thead><tr><th>Name</th><th>Key ID</th><th>Mode</th><th>Status</th><th>Webhook path</th></tr></thead><tbody>
          {merchants.map(m => <tr key={m.id}><td>{m.display_name}</td><td><code>{m.key_id}</code></td><td>{m.mode}</td><td>{m.active ? 'Active' : 'Inactive'}</td><td><code>{m.webhook_path}</code></td></tr>)}
        </tbody></table>}
      <small>Changing the account needs provider approval and the server owner. Earlier payments and refunds always stay with the account they used.</small>
    </article>
  </>
}
