import { useEffect, useState } from 'react'
import { api } from './api'
import { rupees } from './money'

type Refund = {
  id: string; order_id: string; amount_paise: number; reason: string; note: string | null
  status: 'REQUESTED' | 'PENDING' | 'PROCESSED' | 'FAILED'; provider_refund_id: string | null
  requested_by_kind: string; created_at: string; processed_at: string | null; last_error: string | null
  retrying: boolean; next_attempt_at: string | null; retry_until: string | null
}

const time = (value: string | null) => value ? new Date(value).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' }) : '—'

const LABEL: Record<Refund['status'], string> = {
  REQUESTED: 'Waiting to send', PENDING: 'With Razorpay', PROCESSED: 'Refunded', FAILED: 'Failed',
}

export function Refunds() {
  const [rows, setRows] = useState<Refund[]>([]); const [error, setError] = useState(''); const [busy, setBusy] = useState('')
  async function load() { try { setRows(await api<Refund[]>('/staff/refunds')) } catch (e) { setError((e as Error).message) } }
  useEffect(() => { void load() }, [])
  async function retry(refund: Refund) {
    const question = refund.retrying
      ? `Send this ${rupees(refund.amount_paise)} refund to Razorpay again now?`
      : `Send a new refund of ${rupees(refund.amount_paise)} to Razorpay?`
    if (!confirm(question)) return
    setBusy(refund.id); setError('')
    try { await api(`/staff/refunds/${refund.id}/retry`, 'POST'); await load() } catch (e) { setError((e as Error).message) } finally { setBusy('') }
  }
  return <>
    <p className="eyebrow">CANTEEN ADMINISTRATION</p>
    <h1>Refunds</h1>
    <p className="warning">A refund shows as Refunded only after Razorpay confirms it. If Razorpay refuses a refund (most often because the Razorpay balance is too low before settlement), it is retried automatically for up to 4 days before it is marked Failed. Keep a reserve balance in Razorpay to avoid delays.</p>
    {error && <p role="alert" className="error">{error}</p>}
    {rows.length ? <div className="card"><table>
      <thead><tr><th>Requested</th><th>Order</th><th>Amount</th><th>Reason</th><th>Status</th><th></th></tr></thead>
      <tbody>{rows.map(r => <tr key={r.id}>
        <td>{new Date(r.created_at).toLocaleString('en-IN')}</td>
        <td><code>{r.order_id.slice(0, 8)}</code></td>
        <td>{rupees(r.amount_paise)}</td>
        <td>{r.reason.replaceAll('_', ' ').toLowerCase()}{r.note ? ` – ${r.note}` : ''}</td>
        <td>{r.retrying
          ? <>Retrying automatically<br/><small>Next try {time(r.next_attempt_at)} · gives up {time(r.retry_until)}</small></>
          : LABEL[r.status]}
          {r.last_error && <><br/><small>Razorpay said: {r.last_error.replace('PAYMENT_PROVIDER_REJECTED: ', '')}</small></>}</td>
        <td>{(r.status === 'FAILED' || r.retrying) && <button className="secondary" disabled={busy === r.id} onClick={() => retry(r)}>{r.retrying ? 'Retry now' : 'Retry'}</button>}</td>
      </tr>)}</tbody>
    </table></div> : <div className="card empty">No refunds yet.</div>}
  </>
}
