import { useCallback } from 'react'
import { api } from '../api'
import type { SampleHousehold } from '../types'

export function useSample() {
  const load = useCallback((): Promise<SampleHousehold> => api.sample(), [])
  return { load }
}
