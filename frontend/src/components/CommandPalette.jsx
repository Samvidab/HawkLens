
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchPortfolioProperties } from '../lib/portfolioApi'
import ShowcaseModal from './ShowcaseModal'
import './CommandPalette.css'

const commands = [
  { name: 'Open portfolio', path: '/', icon: '⌂' },
  { name: 'Start survey', path: '/start-survey', icon: '◎' },
  { name: 'View survey progress', path: '/survey-in-progress', icon: '◷' },
  { name: 'View survey results', path: '/survey-complete', icon: '✓' },
  { name: 'Open building details', path: '/building', icon: '▦' },
  { name: 'Review investment plan', path: '/plan', icon: '↗' },
  { name: 'View supporting evidence', path: '/survey-evidence', icon: '◇' },
  { name: 'Adjust carbon target', path: '/plan-preferences', icon: '◉' },
  { name: 'Open documents', path: '/documents', icon: '▤' },
  { name: 'View financing', path: '/financing-approval', icon: '$' }
]

export default function CommandPalette() {
  const navigate = useNavigate()
  const inputRef = useRef(null)

  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState(0)
  const [properties, setProperties] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [tourProperty, setTourProperty] = useState(null)

  // Load the same properties shown on the portfolio.
  useEffect(() => {
    if (!open) return

    let cancelled = false
    setLoading(true)
    setError('')

    fetchPortfolioProperties() // the demo portfolio's buildings only (GET /portfolio)
      .then((data) => {
        if (!cancelled) {
          setProperties(data.results || [])
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError('Could not load properties. Check the backend.')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [open])

  useEffect(() => {
    function handleKey(e) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setOpen((current) => !current)
      }

      if (e.key === 'Escape') {
        setOpen(false)
      }
    }

    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [])

  useEffect(() => {
    if (open) inputRef.current?.focus()
  }, [open])

  function closePalette() {
    setOpen(false)
    setQuery('')
    setSelected(0)
  }

  const allItems = [
    ...commands.map((command) => ({
      ...command,
      type: 'page'
    })),
    ...properties.map((property) => ({
      name: property.name || property.id,
      description: property.address || 'Matterport building',
      icon: '▧',
      type: 'property',
      property
    }))
  ]

  const results = allItems.filter((item) => {
    const searchText = [
      item.name,
      item.description || '',
      item.type === 'property' ? item.property.id : ''
    ].join(' ').toLowerCase()

    return searchText.includes(query.trim().toLowerCase())
  })

  function runItem(item) {
    if (!item) return

    closePalette()

    if (item.type === 'property') {
      setTourProperty(item.property)
    } else {
      navigate(item.path)
    }
  }

  function handleInputKey(e) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelected((current) =>
        Math.min(current + 1, Math.max(0, results.length - 1))
      )
    }

    if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelected((current) => Math.max(0, current - 1))
    }

    if (e.key === 'Enter') {
      e.preventDefault()
      runItem(results[selected])
    }
  }

  return (
    <>
      <button
        type="button"
        className="command-trigger"
        onClick={() => setOpen(true)}
      >
        <span>⌕</span>
        <span>Search HawkLens</span>
        <kbd>⌘ K</kbd>
      </button>

      {open && (
        <div
          className="command-overlay"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) closePalette()
          }}
        >
          <div
            className="command-panel"
            role="dialog"
            aria-modal="true"
            aria-label="HawkLens command palette"
          >
            <div className="command-search">
              <span className="command-search-icon">⌕</span>

              <input
                ref={inputRef}
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value)
                  setSelected(0)
                }}
                onKeyDown={handleInputKey}
                placeholder="Search buildings, addresses, pages..."
                aria-label="Search HawkLens"
              />

              <button type="button" onClick={closePalette}>
                ESC
              </button>
            </div>

            <div className="command-results">
              <p className="command-section-title">
                {query ? 'SEARCH RESULTS' : 'PAGES & BUILDINGS'}
              </p>

              {loading && (
                <p className="command-empty">Loading buildings...</p>
              )}

              {error && (
                <p className="command-empty">{error}</p>
              )}

              {!loading && results.length === 0 && (
                <p className="command-empty">No results found</p>
              )}

              {results.map((item, index) => (
                <button
                  key={item.type === 'property'
                    ? `property-${item.property.id}`
                    : `page-${item.path}`}
                  type="button"
                  className={`command-item ${
                    selected === index ? 'selected' : ''
                  }`}
                  onMouseEnter={() => setSelected(index)}
                  onClick={() => runItem(item)}
                >
                  <span className="command-icon">
                    {item.icon}
                  </span>

                  <span className="command-item-text">
                    <strong>{item.name}</strong>
                    <small>
                      {item.type === 'property'
                        ? item.description
                        : 'Open page'}
                    </small>
                  </span>

                  <span className="command-arrow">
                    {item.type === 'property' ? '3D ↗' : '↗'}
                  </span>
                </button>
              ))}
            </div>

            <div className="command-footer">
              <span>↑ ↓ Navigate</span>
              <span>↵ Select</span>
              <span>ESC Close</span>
              <span className="command-brand">HAWKLENS / COMMAND</span>
            </div>
          </div>
        </div>
      )}

      {tourProperty && (
        <ShowcaseModal
          property={tourProperty}
          onClose={() => setTourProperty(null)}
        />
      )}
    </>
  )
}
