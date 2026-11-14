// @vitest-environment jsdom
import { act, renderHook, waitFor } from '@testing-library/react'
import React from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import overview from '../test/fixtures/portfolio_overview.json'
import detail from '../test/fixtures/building_detail.json'
import { INERT, RunProvider, useBuildingFocus, useOverview, useRun } from './store'

// A scripted backend: `feed` is what the SSE stream will deliver; `states` are what GET /state answers.
function fakeApi({ events = [], states = [], composeResult = overview, portfolio = { city: 'Houston', buildings: [{ building_id: 'b1', name: 'Sample Tower', hero: true }] } } = {}) {
  const log = []
  let handlers
  let current = null // the server's state.json: compose rewrites its layout, like the real backend
  const api = {
    getPortfolio: vi.fn(async () => portfolio),
    getHealth: vi.fn(async () => ({ nessie_mode: 'stub', engine_mode: 'stub' })),
    startRun: vi.fn(async (goal) => { log.push(['startRun', goal]); return { run_id: 'run_1' } }),
    getState: vi.fn(async (id) => {
      log.push(['getState', id])
      const s = states.length > 1 ? states.shift() : states[0]
      if (s instanceof Error) throw s
      if (!current || states.length > 0 && current._src !== s) current = { ...s, _src: s }
      return current
    }),
    compose: vi.fn(async (id, type, payload) => {
      log.push(['compose', id, type, payload])
      const layout = typeof composeResult === 'function' ? composeResult(type, payload) : composeResult
      if (current) current = { ...current, layout }
      return layout
    }),
    openEvents: vi.fn((id, h) => {
      log.push(['openEvents', id, !!h.replay])
      handlers = h
      queueMicrotask(() => { for (const e of events) { h.onEvent(e); if (e.kind === 'done') h.onDone(e) } })
      return () => log.push(['closeFeed'])
    }),
  }
  return { api, log, handlers: () => handlers }
}
const ev = (seq, kind = 'observe', extra = {}) => ({ seq, kind, agent: 'Aerial', message: `m${seq}`, ...extra })
const wrap = (api, props = {}) => ({ children }) => <RunProvider api={api} {...props}>{children}</RunProvider>
const GOAL = { city: 'Houston', target_pct: 40, risk_lambda: 0.5 }

beforeEach(() => sessionStorage.clear())

describe('useRun without a provider', () => {
  it('is inert, so pages keep their prototype data', async () => {
    const { result } = renderHook(() => useRun())
    expect(result.current).toBe(INERT)
    expect(result.current.layout).toBeNull(); expect(result.current.live).toBe(false)
    expect(await result.current.start(GOAL)).toBeNull()
  })
})

describe('start: POST /run -> SSE -> workspace', () => {
  it('delivers the feed, then loads the state and becomes ready on `done`', async () => {
    const { api, log } = fakeApi({ events: [ev(0), ev(1), ev(2, 'done')], states: [{ status: 'surveyed' }, { status: 'ready', layout: overview, plan_id: 'plan_1', goal: GOAL }] })
    const { result } = renderHook(() => useRun(), { wrapper: wrap(api) })
    let id
    await act(async () => { id = await result.current.start(GOAL) })
    expect(id).toBe('run_1'); expect(api.startRun).toHaveBeenCalledWith(GOAL)
    await waitFor(() => expect(result.current.phase).toBe('ready'), { timeout: 3000 })
    expect(result.current.events.map((e) => e.seq)).toEqual([0, 1, 2])
    expect(result.current.layout.situation).toBe('portfolio_overview'); expect(result.current.state.plan_id).toBe('plan_1')
    expect(sessionStorage.getItem('hawklens.runId')).toBe('run_1')
    expect(log.map((l) => l[0])).toEqual(expect.arrayContaining(['startRun', 'openEvents', 'getState']))
  })

  it('does not duplicate events the stream repeats', async () => {
    const { api, handlers } = fakeApi({ states: [{ status: 'ready', layout: overview }] })
    const { result } = renderHook(() => useRun(), { wrapper: wrap(api) })
    await act(async () => { await result.current.start(GOAL) })
    act(() => { handlers().onEvent(ev(0)); handlers().onEvent(ev(0)); handlers().onEvent(ev(1)) })
    expect(result.current.events.map((e) => e.seq)).toEqual([0, 1])
  })

  it('a start failure sets the error and the error phase', async () => {
    const { api } = fakeApi()
    api.startRun.mockRejectedValue(Object.assign(new Error('Cannot reach the backend'), { status: 0 }))
    const { result } = renderHook(() => useRun(), { wrapper: wrap(api) })
    let id = 'x'
    await act(async () => { id = await result.current.start(GOAL) })
    expect(id).toBeNull(); expect(result.current.phase).toBe('error'); expect(result.current.error).toMatch(/Cannot reach/)
  })

  it('a run that ends without a workspace reports why', async () => {
    const { api } = fakeApi({ events: [ev(0, 'done')], states: [{ status: 'error', error: 'pricing failed' }] })
    const { result } = renderHook(() => useRun(), { wrapper: wrap(api) })
    await act(async () => { await result.current.start(GOAL) })
    await waitFor(() => expect(result.current.phase).toBe('error'), { timeout: 3000 })
    expect(result.current.error).toBe('pricing failed')
  })

  it('replay opens the recorded run, and builds its workspace from the saved goal when it has none', async () => {
    const { api, log } = fakeApi({ events: [ev(0, 'done')], states: [{ status: 'surveyed', goal: GOAL }, { status: 'ready', layout: overview, goal: GOAL }] })
    const { result } = renderHook(() => useRun(), { wrapper: wrap(api, { demoRunId: 'run_demo' }) })
    await act(async () => { await result.current.start(GOAL, { replay: true }) })
    await waitFor(() => expect(result.current.phase).toBe('ready'), { timeout: 4000 })
    expect(api.startRun).not.toHaveBeenCalled()
    expect(log).toContainEqual(['openEvents', 'run_demo', true])
    expect(log).toContainEqual(['compose', 'run_demo', 'goal', GOAL])
  })
})

describe('act: POST /compose', () => {
  async function ready(api) {
    const r = renderHook(() => useRun(), { wrapper: wrap(api) })
    await act(async () => { await r.result.current.start(GOAL) })
    await waitFor(() => expect(r.result.current.phase).toBe('ready'), { timeout: 3000 })
    return r
  }
  const base = { events: [ev(0, 'done')], states: [{ status: 'ready', layout: overview, plan_id: 'plan_1' }] }

  it('sends the action for the current run and replaces the layout; busy goes up and down', async () => {
    const { api, log } = fakeApi({ ...base, composeResult: detail })
    const { result } = await ready(api)
    let layout
    await act(async () => { layout = await result.current.act('open_building', { building_id: 'b1' }) })
    expect(layout).toBe(detail); expect(result.current.layout.situation).toBe('building_detail'); expect(result.current.busy).toBe(0)
    expect(log).toContainEqual(['compose', 'run_1', 'open_building', { building_id: 'b1' }])
  })

  it('an error keeps the old layout and exposes the message', async () => {
    const { api } = fakeApi(base)
    const { result } = await ready(api)
    api.compose.mockRejectedValue(Object.assign(new Error('plan_id is not the current plan'), { status: 409 }))
    await act(async () => { await expect(result.current.act('approve', { plan_id: 'old' })).rejects.toMatchObject({ status: 409 }) })
    expect(result.current.layout.situation).toBe('portfolio_overview'); expect(result.current.error).toMatch(/not the current plan/); expect(result.current.busy).toBe(0)
  })

  it('refuses to act before a run exists', async () => {
    const { api } = fakeApi()
    const { result } = renderHook(() => useRun(), { wrapper: wrap(api) })
    await expect(result.current.act('set_target', { target_pct: 5 })).rejects.toThrow(/start a survey/)
  })
})

describe('resume after a reload', () => {
  it('reloads the remembered run', async () => {
    sessionStorage.setItem('hawklens.runId', 'run_9')
    const { api } = fakeApi({ states: [{ status: 'ready', layout: overview, plan_id: 'p' }] })
    const { result } = renderHook(() => useRun(), { wrapper: wrap(api) })
    await waitFor(() => expect(result.current.phase).toBe('ready'))
    expect(result.current.runId).toBe('run_9'); expect(result.current.layout).toBe(overview); expect(result.current.portfolio.city).toBe('Houston')
    expect(result.current.health.nessie_mode).toBe('stub')
  })
  it('forgets a run the server no longer knows', async () => {
    sessionStorage.setItem('hawklens.runId', 'gone')
    const { api } = fakeApi({ states: [Object.assign(new Error('unknown run'), { status: 404 })] })
    const { result } = renderHook(() => useRun(), { wrapper: wrap(api) })
    await waitFor(() => expect(sessionStorage.getItem('hawklens.runId')).toBeNull())
    expect(result.current.runId).toBeNull()
  })
})

describe('view hooks: the layout depends on what the owner is looking at', () => {
  it('useOverview leaves a building and asks for the portfolio view (once, no loop)', async () => {
    sessionStorage.setItem('hawklens.runId', 'run_1')
    const { api } = fakeApi({ states: [{ status: 'ready', layout: detail }], composeResult: overview })
    const { result } = renderHook(() => ({ run: useOverview() }), { wrapper: wrap(api) })
    await waitFor(() => expect(api.compose).toHaveBeenCalledWith('run_1', 'open_building', { building_id: null }), { timeout: 3000 })
    await waitFor(() => expect(result.current.run.layout.situation).toBe('portfolio_overview'))
    await new Promise((r) => setTimeout(r, 100))
    expect(api.compose).toHaveBeenCalledTimes(1)
  })
  it('useOverview does nothing when the plan is already showing', async () => {
    sessionStorage.setItem('hawklens.runId', 'run_1')
    const { api } = fakeApi({ states: [{ status: 'ready', layout: overview }] })
    const { result } = renderHook(() => useOverview(), { wrapper: wrap(api) })
    await waitFor(() => expect(result.current.layout).toBeTruthy())
    await new Promise((r) => setTimeout(r, 100))
    expect(api.compose).not.toHaveBeenCalled()
  })
  it('useBuildingFocus opens the hero when no building is focused', async () => {
    sessionStorage.setItem('hawklens.runId', 'run_1')
    const { api } = fakeApi({ states: [{ status: 'ready', layout: overview }], composeResult: detail })
    renderHook(() => useBuildingFocus(), { wrapper: wrap(api) })
    await waitFor(() => expect(api.compose).toHaveBeenCalledWith('run_1', 'open_building', { building_id: 'b1' }), { timeout: 3000 })
  })
})
