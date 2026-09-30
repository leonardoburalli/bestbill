import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../api'
import type { CompareRequest, CompareResponse } from '../types'

export const SLOW_AFTER_MS = 4_000

export type ComparisonStatus = 'idle' | 'loading' | 'success' | 'error'

export function useComparison() {
  const [status, setStatus] = useState<ComparisonStatus>('idle')
  const [data, setData] = useState<CompareResponse | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [slow, setSlow] = useState(false)
  const controllerRef = useRef<AbortController | null>(null)
  const slowTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const cancel = useCallback(() => {
    controllerRef.current?.abort()
    controllerRef.current = null
    if (slowTimerRef.current) clearTimeout(slowTimerRef.current)
    slowTimerRef.current = null
  }, [])

  useEffect(() => cancel, [cancel])

  const run = useCallback(
    (req: CompareRequest) => {
      cancel()
      const controller = new AbortController()
      controllerRef.current = controller
      setStatus('loading')
      setError(null)
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
          setError(e instanceof ApiError ? e : new ApiError('Errore imprevisto. Riprova.', 0))
          setStatus('error')
        })
    },
    [cancel],
  )

  const reset = useCallback(() => {
    cancel()
    setStatus('idle')
    setData(null)
    setError(null)
    setSlow(false)
  }, [cancel])

  return { status, data, error, slow, run, reset }
}
