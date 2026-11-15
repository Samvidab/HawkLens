// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import React from 'react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import overview from '../test/fixtures/portfolio_overview.json'
import { RunProvider } from '../lib/store'
import PlanPreferences from './PlanPreferences'

const withRisk = (supported, lambda = 0.2) => {
  const l = JSON.parse(JSON.stringify(overview))
  const tc = l.widgets.find((w) => w.type === 'target_control').props
  tc.risk_supported = supported; tc.risk_lambda = lambda
  return l
}

function setup(layout) {
  sessionStorage.setItem('hawklens.runId', 'run_1')
  let saved = layout
  const api = {
    getPortfolio: vi.fn(async () => ({ city: 'Houston', buildings: [] })), getHealth: vi.fn(async () => ({})),
    getState: vi.fn(async () => ({ status: 'ready', layout: saved, plan_id: 'p1' })),
    compose: vi.fn(async (_id, type, payload) => {
      if (type === 'set_risk') saved = withRisk(true, payload.risk_lambda)
      return saved
    }), openEvents: vi.fn(() => () => {}), startRun: vi.fn(),
  }
  render(<MemoryRouter><RunProvider api={api}><PlanPreferences /></RunProvider></MemoryRouter>)
  return api
}
const chip = (name) => screen.getByRole('button', { name })

beforeEach(() => sessionStorage.clear())
afterEach(cleanup)

describe('risk preference chips', () => {
  it('are disabled, with an explanation, when the engine does not apply risk_lambda', async () => {
    const api = setup(withRisk(false))
    await waitFor(() => expect(api.getState).toHaveBeenCalled())
    await screen.findByText(/not applied by the current pricing engine/)
    for (const n of ['Cautious', 'Balanced', 'Growth']) expect(chip(n).disabled).toBe(true)
    fireEvent.click(chip('Growth'))
    expect(api.compose).not.toHaveBeenCalled()
  })

  it('send set_risk with lambda 0.4 / 0.2 / 0 when the engine applies it (Balanced = 0.2 in the middle)', async () => {
    const api = setup(withRisk(true, 0.2))
    await screen.findByText(/Cautious favours plans with a better worst case/)
    for (const n of ['Cautious', 'Balanced', 'Growth']) expect(chip(n).disabled).toBe(false)
    expect(chip('Balanced').getAttribute('aria-pressed')).toBe('true') // lambda 0.2 is shown as Balanced
    fireEvent.click(chip('Cautious')); await waitFor(() => expect(api.compose).toHaveBeenLastCalledWith('run_1', 'set_risk', { risk_lambda: 0.4 }))
    await waitFor(() => expect(chip('Cautious').getAttribute('aria-pressed')).toBe('true'))
    fireEvent.click(chip('Growth')); await waitFor(() => expect(api.compose).toHaveBeenLastCalledWith('run_1', 'set_risk', { risk_lambda: 0 }))
    fireEvent.click(chip('Balanced')); await waitFor(() => expect(api.compose).toHaveBeenLastCalledWith('run_1', 'set_risk', { risk_lambda: 0.2 }))
    expect(api.compose).toHaveBeenCalledTimes(3)
  })

  it('shows the loaded plan\'s own risk position and budget (it arrives after the first render)', async () => {
    setup(withRisk(true, 0))
    await waitFor(() => expect(chip('Growth').getAttribute('aria-pressed')).toBe('true'))
    expect(chip('Balanced').getAttribute('aria-pressed')).toBe('false')
    expect(screen.getByText(/Budget No cap · Growth risk/)).toBeTruthy()
  })

  it('without a run (prototype) the chips still work locally', () => {
    render(<MemoryRouter><RunProvider api={{ getPortfolio: async () => ({}), getHealth: async () => ({}), getState: vi.fn(), compose: vi.fn(), openEvents: vi.fn(), startRun: vi.fn() }}><PlanPreferences /></RunProvider></MemoryRouter>)
    expect(chip('Growth').disabled).toBe(false)
    fireEvent.click(chip('Growth')); expect(chip('Growth').getAttribute('aria-pressed')).toBe('true')
  })
})
