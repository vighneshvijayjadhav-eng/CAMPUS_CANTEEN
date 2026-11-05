import { useEffect, useState } from 'react'
import { api } from './api'

type Photo = { id: string; url: string; width: number; height: number }
type Report = { reason: string; note: string | null; created_at: string }
type Review = {
  id: string; item_name: string | null; rating: number; body: string | null; status: string
  created_at: string; edited: boolean; photos: Photo[]; reports: Report[]; counted_reports: number
}

const stars = (n: number) => '★'.repeat(n) + '☆'.repeat(5 - n)

export function Reviews() {
  const [status, setStatus] = useState<'HIDDEN' | 'VISIBLE'>('HIDDEN')
  const [rows, setRows] = useState<Review[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')

  async function load() {
    setError('')
    try { setRows(await api<Review[]>(`/staff/reviews?status=${status}`)) } catch (e) { setError((e as Error).message) }
  }
  useEffect(() => { void load() }, [status])

  async function decide(review: Review, action: 'restore' | 'remove', note: string) {
    if (action === 'remove' && !confirm('Remove this review permanently? Its photos are deleted and it cannot be restored.')) return
    setBusy(review.id)
    try { await api(`/staff/reviews/${review.id}/${action}`, 'POST', { note: note || null }); await load() }
    catch (e) { setError((e as Error).message) }
    finally { setBusy('') }
  }

  return <>
    <p className="eyebrow">CANTEEN ADMINISTRATION</p>
    <h1>Reviews</h1>
    <p className="warning">Reviews publish immediately. A review is hidden automatically after 3 reports from different students who have collected food here. Restore it if it is fair, or remove it if it breaks the rules. Every decision is recorded.</p>
    <nav aria-label="Review status">
      {(['HIDDEN', 'VISIBLE'] as const).map(value =>
        <button key={value} className={status === value ? '' : 'secondary'} aria-pressed={status === value} onClick={() => setStatus(value)}>
          {value === 'HIDDEN' ? 'Awaiting moderation' : 'Published'}
        </button>)}
    </nav>
    {error && <p role="alert" className="error">{error}</p>}
    {rows.map(review => <ReviewCard key={review.id} review={review} busy={busy === review.id} onDecide={decide} />)}
    {!rows.length && <div className="card empty">{status === 'HIDDEN' ? 'No reviews are waiting for moderation.' : 'No published reviews yet.'}</div>}
  </>
}

function ReviewCard({ review, busy, onDecide }: { review: Review; busy: boolean; onDecide: (r: Review, a: 'restore' | 'remove', note: string) => void }) {
  const [note, setNote] = useState('')
  return <article className="card">
    <h2>{review.item_name ?? 'Menu item'} <span aria-label={`${review.rating} out of 5 stars`}>{stars(review.rating)}</span></h2>
    <p>{review.body ?? <em>No written comment.</em>}</p>
    {review.photos.length > 0 && <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
      {review.photos.map(photo => <a key={photo.id} href={photo.url} target="_blank" rel="noreferrer">
        <img src={photo.url} alt="Student photo of the item" width={120} height={Math.round(120 * photo.height / photo.width)} style={{ objectFit: 'cover', borderRadius: 8 }} />
      </a>)}
    </div>}
    <small>{new Date(review.created_at).toLocaleString('en-IN')}{review.edited ? ' · edited' : ''}</small>
    {review.reports.length > 0 && <>
      <h3>Reports ({review.counted_reports} counting)</h3>
      <ul>{review.reports.map((report, index) => <li key={index}>{report.reason.toLowerCase()}{report.note ? `: ${report.note}` : ''}</li>)}</ul>
    </>}
    <label>Moderator note (optional)<input maxLength={500} value={note} onChange={event => setNote(event.target.value)} /></label>
    <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
      {review.status === 'HIDDEN' && <button disabled={busy} onClick={() => onDecide(review, 'restore', note)}>Restore</button>}
      <button className="secondary" disabled={busy} onClick={() => onDecide(review, 'remove', note)}>Remove permanently</button>
    </div>
  </article>
}
