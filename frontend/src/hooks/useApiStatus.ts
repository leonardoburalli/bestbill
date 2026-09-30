import { useCallback, useEffect, useState } from 'react'
import { api, ApiError } from '../api'
import type { CatalogMeta, Health } from '../types'

export type ApiStatus = 'checking' | 'waking' | 'ready' | 'no-catalog' | 'unreachable'

export const WAKING_AFTER_MS = 4_000
export const UNREACHABLE_AFTER_MS = 75_000
export const RETRY_DELAY_MS = 2_000

export function useApiStatus() {
  const [status, setStatus] = useState<ApiStatus>('checking')
  const [health, setHealth] = useState<Health | null>(null)
  const [meta, setMeta] = useState<CatalogMeta | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    const timers = new Set<ReturnType<typeof setTimeout>>()
    let cancelled = false
    let timedOut = false
    const later = (fn: () => void, ms: number) => {
      const t = setTimeout(fn, ms)
      timers.add(t)
      return t
    }

    setStatus('checking')
    setHealth(null)
    setMeta(null)

    later(() => {
      if (!cancelled) setStatus((s) => (s === 'checking' ? 'waking' : s))
    }, WAKING_AFTER_MS)
    later(() => {
      timedOut = true
      controller.abort()
    }, UNREACHABLE_AFTER_MS)

    const sleep = (ms: number) => new Promise<void>((resolve) => later(resolve, ms))

    async function run() {
      let h: Health | null = null
      while (!cancelled && !timedOut && !h) {
        try {
          h = await api.health(controller.signal)
        } catch (e) {
          if (cancelled) return
          if (timedOut) break
          if (e instanceof DOMException && e.name === 'AbortError') return
          await sleep(RETRY_DELAY_MS)
        }
      }
      if (cancelled) return
      if (!h) {
        setStatus('unreachable')
        return
      }
      setHealth(h)
      if (!h.catalog_loaded) {
        setStatus('no-catalog')
        return
      }
      try {
        const m = await api.catalogMeta(controller.signal)
        if (cancelled) return
        setMeta(m)
        setStatus('ready')
      } catch (e) {
        if (cancelled) return
        if (e instanceof ApiError && e.status === 503) setStatus('no-catalog')
        else if (timedOut) setStatus('unreachable')
        else setStatus('ready') // health is fine; meta is only informational
      }
    }
    void run()

    return () => {
      cancelled = true
      controller.abort()
      timers.forEach(clearTimeout)
    }
  }, [attempt])

  const retry = useCallback(() => setAttempt((n) => n + 1), [])
  return { status, health, meta, retry }
}
