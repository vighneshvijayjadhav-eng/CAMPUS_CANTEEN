import { useEffect, useState } from 'react'
import { api } from './api'
import { rupees } from './money'

type Refund = {
  id: string; order_id: string; amount_paise: number; reason: string; note: string | null
  status: 'REQUESTED' | 'PENDING' | 'PROCESSED' | 'FAILED'; provider_refund_id: string | null
  requested_by_kind: string; created_at: string; processed_at: string | null; last_error: string | null
}

const LABEL: Record<Refund['status'], string> = {
  REQUESTED: 'Waiting to send', PENDING: 'With Razorpay', PROCESSED: 'Refunded', FAILED: 'Failed',
}

export function Refunds() {
  const [rows, setRows] = useState<Refund[]>([]); const [error, setError] = useState(''); const [busy, setBusy] = useState('')
  async function load() { try { setRows(await api<Refund[]>('/staff/refunds')) } catch (e) { setError((e as Error).message) } }
  useEffect(() => { void load() }, [])
  async function retry(refund: Refund) {
    if (!confirm(`Send a new refund of ${rupees(refund.amount_paise)} to Razorpay?`)) return
    setBusy(refund.id); setError('')
    try { await api(`/staff/refunds/${refund.id}/retry`, 'POST'); await load() } catch (e) { setError((e as Error).message) } finally { setBusy('') }
  }
  return <>
    <p className="eyebrow">CANTEEN ADMINISTRATION</p>
    <h1>Refunds</h1>
    <p className="warning">A refund shows as Refunded only after Razorpay confirms it. Queued and in-progress refunds are re-checked automatically every few minutes.</p>
    {error && <p role="alert" className="error">{error}</p>}
    {rows.length ? <div className="card"><table>
      <thead><tr><th>Requested</th><th>Order</th><th>Amount</th><th>Reason</th><th>Status</th><th></th></tr></thead>
      <tbody>{rows.map(r => <tr key={r.id}>
        <td>{new Date(r.created_at).toLocaleString('en-IN')}</td>
        <td><code>{r.order_id.slice(0, 8)}</code></td>
        <td>{rupees(r.amount_paise)}</td>
        <td>{r.reason.replaceAll('_', ' ').toLowerCase()}{r.note ? ` – ${r.note}` : ''}</td>
        <td>{LABEL[r.status]}{r.last_error ? ` (${r.last_error.replaceAll('_', ' ').toLowerCase()})` : ''}</td>
        <td>{r.status === 'FAILED' && <button className="secondary" disabled={busy === r.id} onClick={() => retry(r)}>Retry</button>}</td>
      </tr>)}</tbody>
    </table></div> : <div className="card empty">No refunds yet.</div>}
  </>
}
