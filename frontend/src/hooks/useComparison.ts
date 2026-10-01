import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../api'
import type { CompareRequest, CompareResponse } from '../types'

export const SLOW_AFTER_MS = 4_000

export type ComparisonStatus = 'idle' | 'loading' | 'success' | 'error'

const toApiError = (e: unknown) => (e instanceof ApiError ? e : new ApiError('Errore imprevisto. Riprova.', 0))

/**
 * One comparison at a time. `run` replaces the data (page 1); `loadMore` asks for the next page
 * (offset = results already loaded) and appends it. Starting any request aborts the one in flight,
 * and a response from an aborted request is dropped, so a late page can never land on newer data.
 */
export function useComparison() {
  const [status, setStatus] = useState<ComparisonStatus>('idle')
  const [data, setDataState] = useState<CompareResponse | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [slow, setSlow] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [moreError, setMoreError] = useState<ApiError | null>(null)
  const controllerRef = useRef<AbortController | null>(null)
  const slowTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const dataRef = useRef<CompareResponse | null>(null)
  const inFlightRef = useRef<'run' | 'more' | null>(null)

  const setData = useCallback((d: CompareResponse | null) => {
    dataRef.current = d
    setDataState(d)
  }, [])

  const cancel = useCallback(() => {
    controllerRef.current?.abort()
    controllerRef.current = null
    inFlightRef.current = null
    if (slowTimerRef.current) clearTimeout(slowTimerRef.current)
    slowTimerRef.current = null
    setLoadingMore(false)
  }, [])

  useEffect(() => cancel, [cancel])

  const run = useCallback(
    (req: CompareRequest) => {
      cancel()
      const controller = new AbortController()
      controllerRef.current = controller
      inFlightRef.current = 'run'
      setStatus('loading')
      setError(null)
      setMoreError(null)
      setSlow(false)
      slowTimerRef.current = setTimeout(() => setSlow(true), SLOW_AFTER_MS)
      api
        .compare(req, controller.signal)
        .then((res) => {
          if (controller.signal.aborted) return
          cancel()
          setData(res)
          setSlow(false)
          setStatus('success')
        })
        .catch((e: unknown) => {
          if (controller.signal.aborted) return
          if (e instanceof DOMException && e.name === 'AbortError') return
          cancel()
          setSlow(false)
          setError(toApiError(e))
          setStatus('error')
        })
    },
    [cancel, setData],
  )

  /** Next page. Ignored while another request is in flight or when there is nothing loaded yet.
   *  The caller passes the same request as the data on screen; the offset is added here. */
  const loadMore = useCallback(
    (req: CompareRequest) => {
      const base = dataRef.current
      if (!base || inFlightRef.current) return
      const controller = new AbortController()
      controllerRef.current = controller
      inFlightRef.current = 'more'
      setLoadingMore(true)
      setMoreError(null)
      api
        .compare({ ...req, offset: base.results.length }, controller.signal)
        .then((res) => {
          if (controller.signal.aborted) return
          cancel()
          const seen = new Set(base.results.map((r) => r.offer_id))
          setData({ ...res, results: [...base.results, ...res.results.filter((r) => !seen.has(r.offer_id))] })
        })
        .catch((e: unknown) => {
          if (controller.signal.aborted) return
          if (e instanceof DOMException && e.name === 'AbortError') return
          cancel()
          setMoreError(toApiError(e))
        })
    },
    [cancel, setData],
  )

  const reset = useCallback(() => {
    cancel()
    setStatus('idle')
    setData(null)
    setError(null)
    setMoreError(null)
    setSlow(false)
  }, [cancel, setData])

  return { status, data, error, slow, loadingMore, moreError, run, loadMore, reset }
}
