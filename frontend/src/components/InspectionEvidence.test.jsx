// @vitest-environment jsdom
import React from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import InspectionEvidence, { evidenceMarks, NO_IMAGE_LOCATION } from './InspectionEvidence'
import audit from '../../../docs/agent/fixture-placement-audit.json'

const item = { equipment: 'troffer', image_id: 'faceA', image_url: '/media/faceA',
  claim: { evidence_ids: ['faceA'], field: 'interior.lighting', value: 'fluorescent' }, verifier: { status: 'verified' },
  image_marks: [{ image_id: 'faceA', label: 'troffer', bbox: [0.2, 0.1, 0.6, 0.5] }] }
afterEach(cleanup)
const load = () => {
  const image = screen.getByTestId('evidence-image')
  Object.defineProperties(image, { naturalWidth: { value: 2048 }, naturalHeight: { value: 2048 } })
  fireEvent.load(image)
}

describe('recorded evidence', () => {
  it('uses the original image, with a native-size view and overlays at the exact stored bbox', () => {
    render(<InspectionEvidence item={item} onClose={vi.fn()} />)
    expect(screen.queryByTestId('evidence-overlay')).toBeNull()
    load()
    const rect = screen.getByTestId('evidence-overlay').querySelector('ellipse')
    expect(rect.getAttribute('cx')).toBe('0.4')
    expect(rect.getAttribute('cy')).toBe('0.3')
    expect(Number(rect.getAttribute('rx'))).toBeCloseTo(0.2)
    expect(Number(rect.getAttribute('ry'))).toBeCloseTo(0.2)
    expect(rect.getAttribute('vector-effect')).toBe('non-scaling-stroke')
    const img = screen.getByTestId('evidence-image')
    expect(img.getAttribute('src')).toContain('/media/faceA')
    expect(img.style.width).toBe('auto')
    fireEvent.click(screen.getByText('View at original size (1:1)'))
    expect(img.style.maxWidth).toBe('none')
    expect(img.style.maxHeight).toBe('none')
    expect(screen.getByTestId('evidence-image-scroll').style.textAlign).toBe('left')
    expect(screen.getByTestId('evidence-overlay').getAttribute('viewBox')).toBe('0 0 1 1')
  })

  it('offers explicit return to the unchanged 3D tour and magnifies original pixels without changing the image source', () => {
    const close = vi.fn()
    render(<InspectionEvidence item={item} onClose={close} />)
    load()
    const image = screen.getByTestId('evidence-image')
    const src = image.getAttribute('src')
    fireEvent.click(screen.getByText('View at original size (1:1)'))
    image.getBoundingClientRect = () => ({ left: 0, top: 0, width: Number.parseFloat(image.style.width), height: Number.parseFloat(image.style.height) })
    fireEvent.click(screen.getByText('Zoom in'))
    expect(image.style.width).toBe('2560px')
    expect(image.getAttribute('src')).toBe(src)
    expect(screen.getByTestId('evidence-zoom').textContent).toBe('125%')
    fireEvent.click(screen.getByText('1:1 pixels'))
    expect(image.style.width).toBe('2048px')
    fireEvent.click(screen.getByTestId('return-to-tour'))
    expect(close).toHaveBeenCalledOnce()
  })

  it.each([[], [{ image_id: 'another', bbox: [0, 0, 1, 1] }],
    [{ image_id: 'faceA', bbox: [-0.1, 0, 1, 1] }], [{ image_id: 'faceA', bbox: [0.9, 0, 0.1, 1] }],
    [{ image_id: 'faceA', bbox: [0, 0, NaN, 1] }]].map((marks) => ({ marks })))('never draws missing, mismatched or invalid coordinates: %j', ({ marks }) => {
    render(<InspectionEvidence item={{ ...item, image_marks: marks }} onClose={vi.fn()} />)
    load()
    expect(screen.getByText(NO_IMAGE_LOCATION)).toBeTruthy()
    expect(screen.queryByTestId('evidence-overlay')).toBeNull()
  })

  it('requires verified claim evidence, and accepts a real nondegenerate polygon', () => {
    expect(evidenceMarks({ ...item, verifier: { status: 'rejected' } })).toEqual([])
    expect(evidenceMarks({ ...item, claim: { evidence_ids: [] } })).toEqual([])
    const polygon = [[0.1, 0.1], [0.2, 0.2], [0.4, 0.1]]
    expect(evidenceMarks({ ...item, image_marks: [{ image_id: 'faceA', polygon }] })[0].polygon).toEqual(polygon)
    expect(evidenceMarks({ ...item, image_marks: [{ image_id: 'faceA', polygon: [[0, 0], [0.1, 0.1], [0.2, 0.2]] }] })).toEqual([])
  })

  it('renders all recorded marks instead of inventing one representative object', () => {
    render(<InspectionEvidence item={{ ...item, image_marks: [...item.image_marks, ...item.image_marks] }} onClose={vi.fn()} />)
    load()
    expect(screen.getAllByTestId('evidence-mark')).toHaveLength(2)
  })

  it('hides overlays when the evidence image fails', () => {
    render(<InspectionEvidence item={item} onClose={vi.fn()} />)
    fireEvent.error(screen.getByTestId('evidence-image'))
    expect(screen.getByRole('alert')).toBeTruthy()
    expect(screen.queryByTestId('evidence-overlay')).toBeNull()
  })

  it('audits all 23 recorded tags across seven buildings', () => {
    const items = audit.buildings.flatMap((b) => b.observations)
    expect(items).toHaveLength(23)
    for (const i of items) {
      const marks = evidenceMarks({ ...i, verifier: { status: 'verified' }, claim: { evidence_ids: [i.image_id] } })
      expect(marks.length).toBeGreaterThan(0)
      expect(marks.every((m) => i.image_marks.some((recorded) => recorded.bbox === m.bbox))).toBe(true)
    }
  })
})
