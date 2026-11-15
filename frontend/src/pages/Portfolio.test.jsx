// @vitest-environment jsdom
import React from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import inventory from '../../../docs/agent/samples/portfolio.json'
import { PortfolioModel } from './Portfolio'
afterEach(cleanup)
it('renders the recorded inventory and retains building identity for tour and detail actions', () => {
  const onTour = vi.fn(), onDetails = vi.fn()
  const { container } = render(<PortfolioModel buildings={inventory.buildings} onTour={onTour} onDetails={onDetails} hasRun />)
  expect(container.querySelectorAll('[data-building-id]').length).toBe(inventory.buildings.length)
  for (const b of inventory.buildings) {
    expect(screen.getByRole('heading', { name: b.name })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: `Open tour of ${b.name}` }))
    expect(onTour).toHaveBeenLastCalledWith(b)
    fireEvent.click(screen.getByRole('button', { name: `Details for ${b.name}` }))
    expect(onDetails).toHaveBeenLastCalledWith(b.building_id)
  }
})
it('missing fields have explicit unavailable states and cannot open an invented tour', () => {
  const b = { building_id: inventory.buildings[0].building_id }
  const { container } = render(<PortfolioModel buildings={[b]} onTour={vi.fn()} onDetails={vi.fn()} hasRun={false} />)
  for (const label of ['Name not available', 'Address not available', 'Area not available', 'Thumbnail not available']) expect(screen.getByText(label)).toBeTruthy()
  expect(screen.getByRole('button', { name: `Open tour of ${b.building_id}` }).disabled).toBe(true)
  expect(container.querySelectorAll('img').length).toBe(0)
})
