import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { Comune } from '../types'

export const COMUNI_DEBOUNCE_MS = 250
export const COMUNI_MIN_CHARS = 2

export function useComuniSearch() {
  const [query, setQueryState] = useState('')
  const [results, setResults] = useState<Comune[]>([])
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState<Comune | null>(null)
  const selectedLabel = useRef<string | null>(null)

  useEffect(() => {
    if (selectedLabel.current === query) return // query set by select(), don't search
    const q = query.trim()
    if (q.length < COMUNI_MIN_CHARS) {
      setResults([])
      setLoading(false)
      return
    }
    const controller = new AbortController()
    setLoading(true)
    const timer = setTimeout(() => {
      api
        .comuni(q, controller.signal)
        .then((r) => {
          setResults(r)
          setLoading(false)
        })
        .catch((e) => {
          if (e instanceof DOMException && e.name === 'AbortError') return
          setResults([])
          setLoading(false)
        })
    }, COMUNI_DEBOUNCE_MS)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [query])

  const setQuery = useCallback((q: string) => {
    selectedLabel.current = null
    setSelected(null) // typing after select clears the selection
    setQueryState(q)
  }, [])

  const select = useCallback((c: Comune) => {
    const label = `${c.nome} (${c.sigla_provincia})`
    selectedLabel.current = label
    setSelected(c)
    setQueryState(label)
    setResults([])
    setLoading(false)
  }, [])

  const clear = useCallback(() => {
    selectedLabel.current = null
    setSelected(null)
    setQueryState('')
    setResults([])
    setLoading(false)
  }, [])

  return { query, setQuery, results, loading, selected, select, clear }
}
