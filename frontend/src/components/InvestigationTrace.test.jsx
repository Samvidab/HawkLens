// @vitest-environment jsdom
// The investigator's steps: numbered, each recorded feed line verbatim with its quoted facts and image thumbnails;
// no trace -> "not available". (Synthetic test data.)
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import React from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import InvestigationTrace from './InvestigationTrace'

// a plain function, not vi.fn: the spy keeps its own handle on a returned rejected promise and reports it as unhandled
const m = vi.hoisted(() => ({ calls: [], impl: null }))
vi.mock('../lib/api', async (orig) => ({ ...(await orig()), getInvestigationTrace: (id) => { m.calls.push(id); return m.impl(id) }, mediaUrl: (id) => `http://api/media/${id}` }))

const TRACE = { steps: [
  { feed_line: 'inspected roof: for solar, given built 1983', tool: 'inspect_roof',
    facts_quoted: [{ id: 'built', text: 'built 1983', source: 'CoStar record' }], image_ids: ['vxo_1'] },
  { feed_line: 'listed 3 rooms, 17 panoramas', tool: 'get_matterport_rooms', facts_quoted: [], image_ids: [] },
  { feed_line: 'looked inside: fluorescent lighting', tool: 'inspect_interior', facts_quoted: [], image_ids: ['mpp_a_0', 'mpp_b_0'] },
] }

beforeEach(() => { m.calls = []; m.impl = null })
afterEach(cleanup)

it('numbered steps, feed lines verbatim, quoted facts with source, thumbnails from /media', async () => {
  m.impl = async () => TRACE
  render(<InvestigationTrace buildingId="b1" />)
  await waitFor(() => expect(document.querySelectorAll('[data-trace-step]')).toHaveLength(3))
  expect(m.calls).toEqual(['b1'])
  const steps = [...document.querySelectorAll('[data-trace-step]')]
  expect(steps.map((s) => s.getAttribute('data-trace-step'))).toEqual(['1', '2', '3'])
  expect(steps[0].textContent).toContain('1.')
  expect(steps[0].textContent).toContain('inspected roof: for solar, given built 1983')
  expect(steps[0].textContent).toContain('“built 1983” (CoStar record)')
  expect([...document.querySelectorAll('[data-trace-image]')].map((i) => i.getAttribute('src')))
    .toEqual(['http://api/media/vxo_1', 'http://api/media/mpp_a_0', 'http://api/media/mpp_b_0'])
})

it('no trace -> not available, no list', async () => {
  m.impl = () => Promise.reject(Object.assign(new Error('no trace'), { status: 404 }))
  render(<InvestigationTrace buildingId="b1" />)
  await waitFor(() => expect(screen.getByTestId('trace-na')).toBeTruthy())
  expect(document.querySelectorAll('[data-trace-step]')).toHaveLength(0)
})
