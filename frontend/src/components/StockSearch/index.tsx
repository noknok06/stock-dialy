import React, { useState, useCallback, useRef, useEffect } from 'react'
import type { Company, HiddenFieldMap, StockSearchProps } from './types'

function debounce<T extends (...args: Parameters<T>) => void>(fn: T, delay: number) {
  let timer: ReturnType<typeof setTimeout>
  return (...args: Parameters<T>) => {
    clearTimeout(timer)
    timer = setTimeout(() => fn(...args), delay)
  }
}

function setFieldValue(id: string | undefined, value: string) {
  if (!id) return
  const el = document.getElementById(id) as HTMLInputElement | null
  if (el) {
    el.value = value
    // Dispatch change event so other listeners (e.g. HTMX) can react
    el.dispatchEvent(new Event('change', { bubbles: true }))
  }
}

export default function StockSearch({
  apiUrl,
  priceApiUrl,
  inputId,
  inputName,
  hiddenFields,
  placeholder = '例: トヨタ自動車 または 7203',
  minChars = 2,
}: StockSearchProps) {
  const [query, setQuery] = useState('')
  const [suggestions, setSuggestions] = useState<Company[]>([])
  const [loading, setLoading] = useState(false)
  const [isOpen, setIsOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const containerRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const fetchSuggestions = useCallback(
    debounce(async (q: string) => {
      if (q.length < minChars) {
        setSuggestions([])
        setIsOpen(false)
        return
      }

      abortRef.current?.abort()
      abortRef.current = new AbortController()

      setLoading(true)
      try {
        const url = `${apiUrl}?query=${encodeURIComponent(q)}&limit=5`
        const res = await fetch(url, { signal: abortRef.current.signal })
        const data = await res.json()
        if (data.success) {
          setSuggestions(data.companies)
          setIsOpen(data.companies.length > 0)
          setActiveIndex(-1)
        }
      } catch (err) {
        if ((err as Error).name !== 'AbortError') {
          setSuggestions([])
          setIsOpen(false)
        }
      } finally {
        setLoading(false)
      }
    }, 300),
    [apiUrl, minChars],
  )

  const selectCompany = useCallback(
    async (company: Company) => {
      setQuery(company.name)
      setSuggestions([])
      setIsOpen(false)
      setActiveIndex(-1)

      // Populate hidden form fields
      setFieldValue(hiddenFields.code, company.code)
      setFieldValue(hiddenFields.name, company.name)
      setFieldValue(hiddenFields.industry, company.industry)
      setFieldValue(hiddenFields.market, company.market)

      // Auto-fill current price if price field is configured
      if (hiddenFields.price && company.code) {
        try {
          const res = await fetch(`${priceApiUrl}${company.code}/`)
          const data = await res.json()
          const price = data.price ?? data.current_price
          if (data.success && price != null) {
            setFieldValue(hiddenFields.price, String(price))
          }
        } catch {
          // Price fetch failure is non-critical
        }
      }
    },
    [hiddenFields, priceApiUrl],
  )

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!isOpen) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIndex((i) => Math.min(i + 1, suggestions.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIndex((i) => Math.max(i - 1, -1))
    } else if (e.key === 'Enter' && activeIndex >= 0) {
      e.preventDefault()
      selectCompany(suggestions[activeIndex])
    } else if (e.key === 'Escape') {
      setIsOpen(false)
    }
  }

  return (
    <div ref={containerRef} style={{ position: 'relative' }}>
      <input
        type="text"
        id={inputId}
        name={inputName}
        className="form-control form-control-lg"
        placeholder={placeholder}
        value={query}
        autoComplete="off"
        aria-autocomplete="list"
        aria-expanded={isOpen}
        aria-controls={`${inputId}_listbox`}
        aria-describedby={`${inputId}_help`}
        onChange={(e) => {
          const v = e.target.value
          setQuery(v)
          fetchSuggestions(v)
        }}
        onKeyDown={handleKeyDown}
      />

      {loading && (
        <span
          style={{
            position: 'absolute',
            right: '12px',
            top: '50%',
            transform: 'translateY(-50%)',
            fontSize: '0.75rem',
            color: '#6c757d',
          }}
        >
          <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true" />
        </span>
      )}

      {isOpen && suggestions.length > 0 && (
        <div
          id={`${inputId}_listbox`}
          className="suggestions-inline"
          role="listbox"
          style={{ display: 'block' }}
        >
          <div className="suggestions-list">
            {suggestions.map((company, idx) => (
              <div
                key={company.code}
                className={`suggestion-item${idx === activeIndex ? ' active' : ''}`}
                role="option"
                aria-selected={idx === activeIndex}
                onMouseDown={(e) => {
                  // Prevent blur before click registers
                  e.preventDefault()
                  selectCompany(company)
                }}
                onMouseEnter={() => setActiveIndex(idx)}
              >
                <span className="company-code">{company.code}</span>
                <span className="company-name">{company.name}</span>
                {company.industry && (
                  <span className="company-industry text-muted">{company.industry}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export type { HiddenFieldMap, StockSearchProps }
