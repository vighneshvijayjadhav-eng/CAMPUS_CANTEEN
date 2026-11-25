import { useEffect, useMemo, useState } from 'react'
import { api, type Item, type Station, type Variant } from './api'
import { rupees } from './money'

type Status = 'available' | 'unavailable' | 'check'

const STATUS_LABEL: Record<Status, string> = {
  available: 'Available',
  unavailable: 'Unavailable',
  check: 'Needs check',
}

function statusOf(v: Variant): Status {
  if (!v.verified) return 'check'
  return v.available ? 'available' : 'unavailable'
}

/** Status maps onto the server's verified/available pair; "available" needs a price and counter. */
function withStatus(v: Variant, status: Status): Variant {
  if (status === 'check') return { ...v, verified: false, available: false }
  return { ...v, verified: true, available: status === 'available' }
}

// Show sizes largest first so an item's name sits on its first row.
const SIZE_ORDER = ['jumbo', 'large', 'regular', 'medium', 'small']
const sizeRank = (label: string) => {
  const index = SIZE_ORDER.indexOf(label.trim().toLowerCase())
  return index === -1 ? SIZE_ORDER.length : index
}
const sortedVariants = (item: Item) =>
  [...item.variants].sort((a, b) => sizeRank(a.label) - sizeRank(b.label) || a.label.localeCompare(b.label))

const toPaise = (value: string) => (value.trim() === '' ? null : Math.round(Number(value) * 100))
const toRupeeInput = (paise: number | null) => (paise == null ? '' : String(paise / 100))

function PriceCell({ variant, onSave }: { variant: Variant; onSave: (v: Variant) => Promise<void> }) {
  const [value, setValue] = useState(toRupeeInput(variant.price_paise))
  useEffect(() => setValue(toRupeeInput(variant.price_paise)), [variant.price_paise])
  async function commit() {
    const paise = toPaise(value)
    if (paise === variant.price_paise) return
    if (paise != null && (!Number.isFinite(paise) || paise <= 0)) { setValue(toRupeeInput(variant.price_paise)); return }
    await onSave({ ...variant, price_paise: paise, available: paise == null ? false : variant.available })
  }
  return <div className="m-price">
    <span>₹</span>
    <input aria-label="Price in rupees" inputMode="decimal" value={value} placeholder="—"
      onChange={e => setValue(e.target.value)} onBlur={commit}
      onKeyDown={e => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur() }} />
  </div>
}

function VariantRow({ item, variant, first, stations, onSave, onOpen }: {
  item: Item; variant: Variant; first: boolean; stations: Station[]
  onSave: (v: Variant) => Promise<void>; onOpen: () => void
}) {
  const status = statusOf(variant)
  const canBeAvailable = !!variant.price_paise && !!variant.station_id
  return <tr className={item.archived ? 'm-archived' : ''}>
    <td className="m-name">{first && <button className="m-link" onClick={onOpen}>{item.name}</button>}</td>
    <td className="m-size">{variant.label}</td>
    <td><PriceCell variant={variant} onSave={onSave} /></td>
    <td>
      <select aria-label={`Counter for ${item.name} ${variant.label}`} className={variant.station_id ? '' : 'm-missing'}
        value={variant.station_id ?? ''}
        onChange={e => onSave({ ...variant, station_id: e.target.value || null, available: e.target.value ? variant.available : false })}>
        <option value="">No counter</option>
        {stations.map(s => <option key={s.id} value={s.id} disabled={!s.active}>{s.name}{s.active ? '' : ' (off)'}</option>)}
      </select>
    </td>
    <td>
      <select aria-label={`Status of ${item.name} ${variant.label}`} className={`m-status m-${status}`} value={status}
        onChange={e => onSave(withStatus(variant, e.target.value as Status))}>
        <option value="available" disabled={!canBeAvailable}>Available</option>
        <option value="unavailable">Unavailable</option>
        <option value="check">Needs check</option>
      </select>
    </td>
    <td className="m-actions">{first && <button className="m-ghost" onClick={onOpen}>Edit</button>}</td>
  </tr>
}

function ItemPanel({ item, stations, categories, onClose, onChanged }: {
  item: Item | null; stations: Station[]; categories: string[]; onClose: () => void; onChanged: () => Promise<void>
}) {
  const [name, setName] = useState(item?.name ?? '')
  const [category, setCategory] = useState(item?.category ?? '')
  const [size, setSize] = useState({ label: '', price: '', station: '' })
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false)

  async function run(action: () => Promise<unknown>, close = false) {
    setBusy(true); setError('')
    try { await action(); await onChanged(); if (close) onClose() }
    catch (e) { setError((e as Error).message) }
    finally { setBusy(false) }
  }
  const saveItem = (e: React.FormEvent) => {
    e.preventDefault()
    run(() => api(item ? `/staff/menu/${item.id}` : '/staff/menu', item ? 'PATCH' : 'POST',
      { name, category, archived: item?.archived ?? false }), !item)
  }
  const addSize = (e: React.FormEvent) => {
    e.preventDefault()
    if (!item) return
    run(async () => {
      await api(`/staff/menu/${item.id}/variants`, 'POST', {
        label: size.label, price_paise: toPaise(size.price), station_id: size.station || null,
        verified: false, available: false,
      })
      setSize({ label: '', price: '', station: '' })
    })
  }

  return <div className="m-overlay" role="presentation" onClick={onClose}>
    <aside className="m-panel" role="dialog" aria-modal="true" aria-label={item ? `Edit ${item.name}` : 'New menu item'} onClick={e => e.stopPropagation()}>
      <header><h2>{item ? item.name : 'New menu item'}</h2><button className="m-ghost" onClick={onClose} aria-label="Close">✕</button></header>
      {item?.source_sheet && <p className="m-hint">From the menu workbook: {item.source_sheet}, row {item.source_row}</p>}
      {error && <p className="error" role="alert">{error}</p>}
      <form onSubmit={saveItem} className="m-form">
        <label>Name<input value={name} onChange={e => setName(e.target.value)} required maxLength={160} /></label>
        <label>Category<input value={category} onChange={e => setCategory(e.target.value)} required maxLength={120} list="m-categories" /></label>
        <datalist id="m-categories">{categories.map(c => <option key={c} value={c} />)}</datalist>
        <button disabled={busy}>{item ? 'Save details' : 'Create item'}</button>
      </form>
      {item && <>
        <h3>Sizes</h3>
        <p className="m-hint">Edit prices, counters and status directly in the menu table. New sizes start as "Needs check".</p>
        <ul className="m-sizes">{item.variants.map(v => <li key={v.id}><span>{v.label}</span><span>{v.price_paise ? rupees(v.price_paise) : 'No price'}</span><span className={`m-pill m-${statusOf(v)}`}>{STATUS_LABEL[statusOf(v)]}</span></li>)}</ul>
        <form onSubmit={addSize} className="m-form m-inline">
          <label>Size<input value={size.label} onChange={e => setSize({ ...size, label: e.target.value })} placeholder="e.g. Small" required maxLength={80} /></label>
          <label>Price (₹)<input value={size.price} onChange={e => setSize({ ...size, price: e.target.value })} inputMode="decimal" placeholder="40" /></label>
          <label>Counter<select value={size.station} onChange={e => setSize({ ...size, station: e.target.value })}>
            <option value="">No counter</option>{stations.filter(s => s.active).map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select></label>
          <button disabled={busy}>Add size</button>
        </form>
        <div className="m-danger">
          <div><strong>{item.archived ? 'Archived' : 'Archive item'}</strong><p className="m-hint">{item.archived ? 'Hidden from students. Restore to show it again.' : 'Hides it from students without deleting order history.'}</p></div>
          <button className="secondary" disabled={busy}
            onClick={() => run(() => api(`/staff/menu/${item.id}`, 'PATCH', { name: item.name, category: item.category, archived: !item.archived }))}>
            {item.archived ? 'Restore' : 'Archive'}
          </button>
        </div>
      </>}
    </aside>
  </div>
}

export function Menu() {
  const [items, setItems] = useState<Item[]>([]); const [stations, setStations] = useState<Station[]>([])
  const [search, setSearch] = useState(''); const [category, setCategory] = useState('')
  const [counter, setCounter] = useState(''); const [status, setStatus] = useState('')
  const [showArchived, setShowArchived] = useState(false)
  const [editing, setEditing] = useState<Item | null | undefined>(undefined)
  const [error, setError] = useState(''); const [saved, setSaved] = useState('')

  async function load() {
    try {
      const [menu, counters] = await Promise.all([api<Item[]>('/staff/menu'), api<Station[]>('/staff/stations')])
      setItems(menu); setStations(counters)
      setEditing(current => current ? menu.find(i => i.id === current.id) ?? undefined : current)
    } catch (e) { setError((e as Error).message) }
  }
  useEffect(() => { void load() }, [])

  async function saveVariant(v: Variant) {
    setError('')
    try {
      const { id, ...body } = v
      await api(`/staff/variants/${id}`, 'PATCH', body)
      setSaved('Saved'); setTimeout(() => setSaved(''), 1500)
      await load()
    } catch (e) { setError((e as Error).message); await load() }
  }

  const categories = useMemo(() => [...new Set(items.map(i => i.category))].sort(), [items])
  const all = items.flatMap(i => i.archived ? [] : i.variants)
  const counts = {
    available: all.filter(v => statusOf(v) === 'available').length,
    unavailable: all.filter(v => statusOf(v) === 'unavailable').length,
    check: all.filter(v => statusOf(v) === 'check').length,
    unmapped: all.filter(v => !v.station_id).length,
  }

  const query = search.trim().toLowerCase()
  const visible = items.filter(item =>
    (showArchived || !item.archived) &&
    (!category || item.category === category) &&
    (!query || `${item.name} ${item.category}`.toLowerCase().includes(query)) &&
    (!counter && !status || item.variants.some(v =>
      (!counter || (counter === 'none' ? !v.station_id : v.station_id === counter)) &&
      (!status || statusOf(v) === status))))
  const groups = categories.map(c => [c, visible.filter(i => i.category === c)] as const).filter(([, list]) => list.length)

  return <>
    <div className="m-head">
      <div><p className="eyebrow">YOUR CANTEEN</p><h1>Menu</h1></div>
      <button onClick={() => setEditing(null)}>+ Add item</button>
    </div>

    <div className="m-stats" role="group" aria-label="Menu summary">
      {([['available', 'Available'], ['unavailable', 'Unavailable'], ['check', 'Needs check']] as const).map(([key, label]) =>
        <button key={key} className={`m-stat ${status === key ? 'on' : ''}`} aria-pressed={status === key}
          onClick={() => setStatus(status === key ? '' : key)}><strong>{counts[key]}</strong><span>{label}</span></button>)}
      <button className={`m-stat ${counter === 'none' ? 'on' : ''}`} aria-pressed={counter === 'none'}
        onClick={() => setCounter(counter === 'none' ? '' : 'none')}><strong>{counts.unmapped}</strong><span>No counter</span></button>
    </div>

    <div className="m-toolbar">
      <input aria-label="Search menu" placeholder="Search items" value={search} onChange={e => setSearch(e.target.value)} />
      <select aria-label="Category" value={category} onChange={e => setCategory(e.target.value)}>
        <option value="">All categories</option>{categories.map(c => <option key={c}>{c}</option>)}
      </select>
      <select aria-label="Counter" value={counter} onChange={e => setCounter(e.target.value)}>
        <option value="">All counters</option><option value="none">No counter</option>
        {stations.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
      </select>
      <select aria-label="Status" value={status} onChange={e => setStatus(e.target.value)}>
        <option value="">Any status</option>
        {(Object.keys(STATUS_LABEL) as Status[]).map(s => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
      </select>
      <label className="m-toggle"><input type="checkbox" checked={showArchived} onChange={e => setShowArchived(e.target.checked)} />Show archived</label>
      <span className="m-saved" role="status">{saved}</span>
    </div>

    {error && <p className="error" role="alert">{error}</p>}

    <div className="m-table-wrap">
      <table className="m-table">
        <thead><tr><th>Item</th><th>Size</th><th>Price</th><th>Counter</th><th>Status</th><th><span className="sr-only">Actions</span></th></tr></thead>
        {groups.map(([name, list]) => <tbody key={name}>
          <tr className="m-group"><th colSpan={6}>{name}<span>{list.length}</span></th></tr>
          {list.flatMap(item => (item.variants.length ? sortedVariants(item) : [null]).map((variant, index) => variant
            ? <VariantRow key={variant.id} item={item} variant={variant} first={index === 0} stations={stations}
                onSave={saveVariant} onOpen={() => setEditing(item)} />
            : <tr key={item.id}><td className="m-name"><button className="m-link" onClick={() => setEditing(item)}>{item.name}</button></td>
                <td colSpan={4} className="m-hint">No sizes yet</td><td className="m-actions"><button className="m-ghost" onClick={() => setEditing(item)}>Edit</button></td></tr>))}
        </tbody>)}
      </table>
      {!groups.length && <p className="m-empty">No items match these filters.</p>}
    </div>

    {editing !== undefined && <ItemPanel key={editing?.id ?? 'new'} item={editing} stations={stations} categories={categories}
      onClose={() => setEditing(undefined)} onChanged={load} />}
  </>
}
