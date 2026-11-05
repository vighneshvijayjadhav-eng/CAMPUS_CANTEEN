import { useEffect, useState } from 'react'
import { api } from './api'
import { rupees } from './money'

type Period = { period: string; orders: number; gross_paise: number; refunds_paise: number; other_refunds_paise: number; net_paise: number }
type Item = { item: string; variant: string; quantity: number; revenue_paise: number }
type Report = { start: string; end: string; group: string; periods: Period[]; totals: Omit<Period, 'period'>; items: Item[] }

function isoDate(d: Date) { return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10) }

export function Reports() {
  const today = new Date()
  const [start, setStart] = useState(isoDate(new Date(today.getFullYear(), today.getMonth(), 1)))
  const [end, setEnd] = useState(isoDate(today))
  const [group, setGroup] = useState('day')
  const [report, setReport] = useState<Report | null>(null); const [error, setError] = useState('')
  async function load() {
    setError('')
    try { setReport(await api<Report>(`/staff/reports/sales?start=${start}&end=${end}&group=${group}`)) } catch (e) { setError((e as Error).message) }
  }
  useEffect(() => { void load() }, [])
  return <>
    <p className="eyebrow">CANTEEN ADMINISTRATION</p>
    <h1>Sales</h1>
    <form className="card" style={{ display: 'flex', gap: 12, alignItems: 'end', flexWrap: 'wrap' }} onSubmit={e => { e.preventDefault(); void load() }}>
      <label>From<input type="date" value={start} max={end} onChange={e => setStart(e.target.value)} required /></label>
      <label>To<input type="date" value={end} min={start} onChange={e => setEnd(e.target.value)} required /></label>
      <label>Group by<select value={group} onChange={e => setGroup(e.target.value)}>
        <option value="day">Day</option><option value="week">Week (from Monday)</option><option value="month">Month</option>
      </select></label>
      <button>Show</button>
    </form>
    {error && <p role="alert" className="error">{error}</p>}
    {report && <>
      <div className="card"><table>
        <thead><tr><th>{report.group === 'week' ? 'Week of' : report.group === 'month' ? 'Month' : 'Day'}</th><th>Orders</th><th>Gross</th><th>Refunds</th><th>Net</th><th>Other refunds*</th></tr></thead>
        <tbody>
          {report.periods.map(p => <tr key={p.period}><td>{p.period}</td><td>{p.orders}</td><td>{rupees(p.gross_paise)}</td><td>{rupees(p.refunds_paise)}</td><td>{rupees(p.net_paise)}</td><td>{rupees(p.other_refunds_paise)}</td></tr>)}
          {!report.periods.length && <tr><td colSpan={6}>No paid orders or refunds in this range.</td></tr>}
        </tbody>
        <tfoot><tr><th>Total</th><th>{report.totals.orders}</th><th>{rupees(report.totals.gross_paise)}</th><th>{rupees(report.totals.refunds_paise)}</th><th>{rupees(report.totals.net_paise)}</th><th>{rupees(report.totals.other_refunds_paise)}</th></tr></tfoot>
      </table>
      <small>Gross: payments Razorpay captured for orders. Refunds: completed refunds of cancelled orders, on the day they completed. *Other refunds: duplicate or wrong-amount payments returned to students (never counted as sales). Times are India time.</small></div>
      <h2>Item-wise sales</h2>
      <div className="card"><table>
        <thead><tr><th>Item</th><th>Size</th><th>Quantity</th><th>Revenue</th></tr></thead>
        <tbody>
          {report.items.map(i => <tr key={i.item + i.variant}><td>{i.item}</td><td>{i.variant}</td><td>{i.quantity}</td><td>{rupees(i.revenue_paise)}</td></tr>)}
          {!report.items.length && <tr><td colSpan={4}>No items sold in this range.</td></tr>}
        </tbody>
      </table><small>Paid orders in the range, excluding cancelled orders.</small></div>
    </>}
  </>
}
