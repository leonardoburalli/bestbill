import { useSyncExternalStore } from 'react'

/** True quando lo schermo è largo (>= 768px): tabella invece di schede. */
export function useIsWide(query = '(min-width: 768px)'): boolean {
  return useSyncExternalStore(
    (cb) => {
      const mq = window.matchMedia(query)
      mq.addEventListener('change', cb)
      return () => mq.removeEventListener('change', cb)
    },
    () => window.matchMedia(query).matches,
    () => true,
  )
}
