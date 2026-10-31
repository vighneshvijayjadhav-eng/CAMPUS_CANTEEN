import { afterEach, expect, test, vi } from 'vitest'
import { api } from './api'

afterEach(()=>vi.unstubAllGlobals())

test('refreshes once and retries authenticated request',async()=>{
  const mock=vi.fn()
    .mockResolvedValueOnce(new Response('{}',{status:401}))
    .mockResolvedValueOnce(new Response('{}',{status:200}))
    .mockResolvedValueOnce(new Response('{"role":"station"}',{status:200}))
  vi.stubGlobal('fetch',mock)
  expect(await api('/staff/me')).toEqual({role:'station'})
  expect(mock.mock.calls.map(call=>call[0])).toEqual(['/api/v1/staff/me','/api/v1/auth/refresh','/api/v1/staff/me'])
})

test('does not retry forbidden handovers',async()=>{
  const mock=vi.fn().mockResolvedValue(new Response('{"error":"LINE_NOT_FOUND"}',{status:404}))
  vi.stubGlobal('fetch',mock)
  await expect(api('/staff/orders/order/lines/line/confirm','POST',{})).rejects.toThrow('LINE NOT FOUND')
  expect(mock).toHaveBeenCalledTimes(1)
})

test('failed login never enters a refresh loop',async()=>{
  const mock=vi.fn().mockResolvedValue(new Response('{"error":"INVALID_CREDENTIALS"}',{status:401}))
  vi.stubGlobal('fetch',mock)
  await expect(api('/auth/staff/login','POST',{})).rejects.toThrow('INVALID CREDENTIALS')
  expect(mock).toHaveBeenCalledTimes(1)
})
