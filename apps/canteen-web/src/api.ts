let refresh: Promise<Response> | undefined
export async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const options: RequestInit = { method, credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) }
  let response = await fetch('/api/v1' + path, options)
  if (response.status === 401 && !path.startsWith('/auth/')) {
    refresh ??= fetch('/api/v1/auth/refresh', {method:'POST', credentials:'include'}).finally(() => { refresh = undefined })
    if ((await refresh).ok) response = await fetch('/api/v1' + path, options)
  }
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.error?.replaceAll('_', ' ') || `Request failed (${response.status}). Please refresh and try again.`)
  }
  return response.json()
}

export type Identity = { role: 'admin' | 'station'; canteen: string; station_id: string | null }
export type Station = { id: string; name: string; active: boolean }
export type Line = { id: string; name: string; variant: string; station: string; quantity: number; fulfilled: number; remaining: number }
export type Order = { id: string; state: string; exception_status: string | null; lines: Line[] }
export type Variant = {id: string; label: string; price_paise: number | null; station_id: string | null; verified: boolean; available: boolean}
export type Item = { id: string; name: string; category: string; archived: boolean; source_sheet: string | null; source_row: number | null; variants: Variant[] }
