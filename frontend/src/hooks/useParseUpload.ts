import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../api'
import type { ParseResult } from '../types'

export type ParseUploadStatus = 'idle' | 'loading' | 'success' | 'error'

export function useParseUpload() {
  const [status, setStatus] = useState<ParseUploadStatus>('idle')
  const [result, setResult] = useState<ParseResult | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const controllerRef = useRef<AbortController | null>(null)

  useEffect(() => () => controllerRef.current?.abort(), [])

  const upload = useCallback((file: File) => {
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller
    setStatus('loading')
    setError(null)
    setResult(null)
    api
      .parse(file, controller.signal)
      .then((r) => {
        if (controller.signal.aborted) return
        setResult(r)
        setStatus('success')
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) return
        if (e instanceof DOMException && e.name === 'AbortError') return
        setError(e instanceof ApiError ? e : new ApiError('Errore imprevisto. Riprova.', 0))
        setStatus('error')
      })
  }, [])

  const reset = useCallback(() => {
    controllerRef.current?.abort()
    controllerRef.current = null
    setStatus('idle')
    setResult(null)
    setError(null)
  }, [])

  return { status, result, error, upload, reset }
}
