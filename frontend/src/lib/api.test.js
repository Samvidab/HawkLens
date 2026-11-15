import { describe, expect, it, vi } from 'vitest'
import * as api from './api'

const json = (status, body) => ({ ok: status < 400, status, statusText: 'x', json: async () => body })

function stubFetch(handler) {
  const calls = []
  globalThis.fetch = vi.fn(async (url, init = {}) => {
    calls.push({ url, method: init.method, body: init.body ? JSON.parse(init.body) : undefined, headers: init.headers })
    return handler(url, init)
  })
  return calls
}

describe('requests', () => {
  it('startRun POSTs the goal to /run', async () => {
    const calls = stubFetch(() => json(200, { run_id: 'run_1' }))
    expect(await api.startRun({ city: 'Houston', target_pct: 40, risk_lambda: 0.5 })).toEqual({ run_id: 'run_1' })
    expect(calls[0]).toMatchObject({ url: `${api.API_BASE}/run`, method: 'POST', body: { city: 'Houston', target_pct: 40, risk_lambda: 0.5 } })
    expect(calls[0].headers['content-type']).toBe('application/json')
  })

  it('compose sends an OwnerAction {run_id, type, payload}', async () => {
    const calls = stubFetch(() => json(200, { widgets: [] }))
    await api.compose('run_1', 'set_target', { target_pct: 25 })
    await api.compose('run_1', 'open_building', { building_id: null })
    await api.compose('run_1', 'goal')
    expect(calls.map((c) => c.body)).toEqual([
      { run_id: 'run_1', type: 'set_target', payload: { target_pct: 25 } },
      { run_id: 'run_1', type: 'open_building', payload: { building_id: null } },
      { run_id: 'run_1', type: 'goal', payload: {} },
    ])
    expect(calls.every((c) => c.url === `${api.API_BASE}/compose` && c.method === 'POST')).toBe(true)
  })

  it('getState/getPortfolio/getRegistry/getHealth are GETs; ids are URL-encoded', async () => {
    const calls = stubFetch(() => json(200, {}))
    await api.getState('run/1 x'); await api.getPortfolio(); await api.getRegistry(); await api.getHealth()
    expect(calls.map((c) => [c.method, c.url.replace(api.API_BASE, '')])).toEqual([
      ['GET', '/state/run%2F1%20x'], ['GET', '/portfolio'], ['GET', '/registry'], ['GET', '/health']])
    expect(calls[0].body).toBeUndefined()
  })

  it('maps HTTP errors to ApiError with the server detail', async () => {
    stubFetch(() => json(409, { detail: "plan_id 'x' is not the current plan 'y'" }))
    await expect(api.compose('r', 'approve', { plan_id: 'x' })).rejects.toMatchObject({ name: 'ApiError', status: 409, message: expect.stringContaining('not the current plan') })
    stubFetch(() => json(422, { detail: [{ loc: ['body', 'payload', 'target_pct'], msg: 'bad number' }] }))
    await expect(api.compose('r', 'set_target', {})).rejects.toMatchObject({ status: 422, message: 'payload.target_pct: bad number' })
    stubFetch(() => ({ ok: false, status: 500, statusText: 'Server Error', json: async () => { throw new Error('not json') } }))
    await expect(api.getState('r')).rejects.toMatchObject({ status: 500, message: 'Server Error' })
  })

  it('a network failure is an ApiError(0) naming the backend', async () => {
    globalThis.fetch = vi.fn(async () => { throw new TypeError('fetch failed') })
    await expect(api.getHealth()).rejects.toMatchObject({ status: 0, message: expect.stringContaining(api.API_BASE) })
  })

  it('mediaUrl, assetUrl and showcaseSrc build URLs', () => {
    expect(api.mediaUrl('vxo_1')).toBe(`${api.API_BASE}/media/vxo_1`)
    expect(api.assetUrl('/properties/1/thumbnail')).toBe(`${api.API_BASE}/properties/1/thumbnail`)
    expect(api.assetUrl('https://x/y.jpg')).toBe('https://x/y.jpg')
    expect(api.assetUrl(null)).toBeNull()
    expect(api.showcaseSrc('abc')).toBe('https://my.matterport.com/show/?m=abc&play=1')
  })
})

class FakeES {
  static last
  constructor(url) { this.url = url; this.closed = false; FakeES.last = this }
  close() { this.closed = true }
  emit(ev) { this.onmessage({ data: JSON.stringify(ev) }) }
}

describe('openEvents', () => {
  const ev = (seq, kind = 'observe') => ({ seq, kind, agent: 'Aerial', message: `m${seq}` })

  it('delivers events in order and closes on `done` without reporting an error', () => {
    const got = [], done = vi.fn(), err = vi.fn()
    api.openEvents('run_1', { EventSourceImpl: FakeES, onEvent: (e) => got.push(e.seq), onDone: done, onError: err })
    const es = FakeES.last
    expect(es.url).toBe(`${api.API_BASE}/events/run_1`)
    es.emit(ev(0)); es.emit(ev(1)); es.emit(ev(2, 'done'))
    expect(got).toEqual([0, 1, 2]); expect(done).toHaveBeenCalledOnce(); expect(es.closed).toBe(true)
    es.onerror(); expect(err).not.toHaveBeenCalled() // the server ending the stream after `done` is not a failure
  })

  it('a stream that dies before `done` is reported once and closed', () => {
    const err = vi.fn()
    api.openEvents('r', { EventSourceImpl: FakeES, onError: err })
    FakeES.last.onerror()
    expect(err).toHaveBeenCalledOnce(); expect(err.mock.calls[0][0]).toMatchObject({ name: 'ApiError' }); expect(FakeES.last.closed).toBe(true)
  })

  it('replay and delay go in the query string; close() stops reporting', () => {
    const err = vi.fn()
    const close = api.openEvents('r', { replay: true, delay: 0, EventSourceImpl: FakeES, onError: err })
    expect(FakeES.last.url).toBe(`${api.API_BASE}/events/r?replay=1&delay=0`)
    close(); FakeES.last.onerror(); expect(err).not.toHaveBeenCalled()
  })

  it('a replay keeps reading past `done` (actions are recorded after it) and reports the server ending the stream', () => {
    const got = [], done = vi.fn(), end = vi.fn(), err = vi.fn()
    api.openEvents('r', { replay: true, delay: 0, EventSourceImpl: FakeES, onEvent: (e) => got.push(e.seq), onDone: done, onEnd: end, onError: err })
    const es = FakeES.last
    es.emit(ev(0)); es.emit(ev(1, 'done')); es.emit(ev(2)); es.emit(ev(3, 'done'))
    expect(got).toEqual([0, 1, 2, 3]); expect(es.closed).toBe(false); expect(done).toHaveBeenCalledOnce() // onDone only for the first
    es.onerror() // EventSource fires an error when the server ends the stream
    expect(end).toHaveBeenCalledOnce(); expect(err).not.toHaveBeenCalled(); expect(es.closed).toBe(true)
  })

  it('ignores malformed messages', () => {
    const got = []
    api.openEvents('r', { EventSourceImpl: FakeES, onEvent: (e) => got.push(e) })
    FakeES.last.onmessage({ data: 'not json' }); FakeES.last.emit(ev(1))
    expect(got).toHaveLength(1)
  })
})
