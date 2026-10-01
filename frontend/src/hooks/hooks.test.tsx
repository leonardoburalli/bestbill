import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { ApiError } from '../api'
import type { CatalogMeta, CompareRequest, CompareResponse, Comune, Health } from '../types'
import { useApiStatus } from './useApiStatus'
import { useComparison } from './useComparison'
import { useComuniSearch } from './useComuniSearch'

const mocked = vi.hoisted(() => ({
  health: vi.fn<(s?: AbortSignal) => Promise<Health>>(),
  catalogMeta: vi.fn<(s?: AbortSignal) => Promise<CatalogMeta>>(),
  sample: vi.fn(),
  comuni: vi.fn<(q: string, s?: AbortSignal) => Promise<Comune[]>>(),
  compare: vi.fn<(b: CompareRequest, s?: AbortSignal) => Promise<CompareResponse>>(),
}))
// Absolute path: a relative '../api' specifier isn't matched by vi.mock here.
vi.mock('/src/api.ts', async (orig) => ({
  ...(await orig<typeof import('../api')>()),
  api: mocked,
}))

beforeEach(() => {
  vi.useFakeTimers()
  vi.resetAllMocks()
})
afterEach(() => vi.useRealTimers())

const abortable = <T,>(signal?: AbortSignal) =>
  new Promise<T>((_, reject) =>
    signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError'))),
  )

const milano: Comune = { codice: '015146', nome: 'Milano', sigla_provincia: 'MI', regione: 'Lombardia' }

describe('useComuniSearch', () => {
  it('debounces 250ms, needs 2 chars, aborts stale', async () => {
    const signals: AbortSignal[] = []
    mocked.comuni.mockImplementation((_q, signal) => {
      signals.push(signal!)
      return Promise.resolve([milano])
    })
    const { result } = renderHook(() => useComuniSearch())
    act(() => result.current.setQuery('m'))
    await act(() => vi.advanceTimersByTimeAsync(500))
    expect(mocked.comuni).not.toHaveBeenCalled()

    act(() => result.current.setQuery('mi'))
    await act(() => vi.advanceTimersByTimeAsync(200))
    act(() => result.current.setQuery('mil'))
    await act(() => vi.advanceTimersByTimeAsync(200))
    expect(mocked.comuni).not.toHaveBeenCalled()
    await act(() => vi.advanceTimersByTimeAsync(60))
    expect(mocked.comuni).toHaveBeenCalledTimes(1)
    expect(mocked.comuni.mock.calls[0][0]).toBe('mil')
    expect(result.current.results).toEqual([milano])

    // in-flight request aborted when a new query arrives
    mocked.comuni.mockImplementation((_q, signal) => {
      signals.push(signal!)
      return abortable(signal)
    })
    act(() => result.current.setQuery('mila'))
    await act(() => vi.advanceTimersByTimeAsync(260))
    const inflight = signals[signals.length - 1]
    act(() => result.current.setQuery('milan'))
    expect(inflight.aborted).toBe(true)
  })

  it('select sets selected without searching; typing clears it', async () => {
    mocked.comuni.mockResolvedValue([milano])
    const { result } = renderHook(() => useComuniSearch())
    act(() => result.current.select(milano))
    await act(() => vi.advanceTimersByTimeAsync(500))
    expect(mocked.comuni).not.toHaveBeenCalled()
    expect(result.current.selected).toEqual(milano)
    expect(result.current.query).toBe('Milano (MI)')
    act(() => result.current.setQuery('Roma'))
    expect(result.current.selected).toBeNull()
    act(() => result.current.clear())
    expect(result.current.query).toBe('')
  })
})

describe('useComparison', () => {
  const resp = (n: number) => ({ total_eligible: n }) as CompareResponse
  it('aborts the in-flight request on re-run and keeps previous data', async () => {
    const signals: AbortSignal[] = []
    mocked.compare.mockResolvedValueOnce(resp(1))
    const { result } = renderHook(() => useComparison())
    await act(async () => result.current.run({} as never))
    expect(result.current.status).toBe('success')
    expect(result.current.data?.total_eligible).toBe(1)

    mocked.compare.mockImplementation((_b, s) => {
      signals.push(s!)
      return abortable(s)
    })
    act(() => result.current.run({} as never))
    expect(result.current.status).toBe('loading')
    expect(result.current.data?.total_eligible).toBe(1) // stale-while-loading

    mocked.compare.mockImplementation((_b, s) => {
      signals.push(s!)
      return Promise.resolve(resp(2))
    })
    await act(async () => result.current.run({} as never))
    expect(signals[0].aborted).toBe(true)
    expect(result.current.status).toBe('success')
    expect(result.current.data?.total_eligible).toBe(2)
  })

  it('slow flag after 4s; error state exposes ApiError', async () => {
    mocked.compare.mockImplementation((_b, s) => abortable(s))
    const { result } = renderHook(() => useComparison())
    act(() => result.current.run({} as never))
    expect(result.current.slow).toBe(false)
    await act(() => vi.advanceTimersByTimeAsync(4100))
    expect(result.current.slow).toBe(true)

    mocked.compare.mockRejectedValue(new ApiError('bad', 422, [{ field: 'f', message: 'm' }]))
    await act(async () => result.current.run({} as never))
    expect(result.current.status).toBe('error')
    expect(result.current.error?.fieldErrors).toHaveLength(1)
    expect(result.current.slow).toBe(false)
  })
})

describe('useComparison paging', () => {
  const item = (id: string, rank: number) => ({ offer_id: id, rank }) as CompareResponse['results'][number]
  const page = (ids: string[], extra: Partial<CompareResponse> = {}) =>
    ({ total_matching: 5, results: ids.map((id, i) => item(id, i + 1)), ...extra }) as CompareResponse

  it('loadMore asks for offset = loaded count and appends; status stays success', async () => {
    mocked.compare.mockResolvedValueOnce(page(['a', 'b']))
    const { result } = renderHook(() => useComparison())
    await act(async () => result.current.run({ top_n: 2 } as never))
    expect(result.current.data?.results.map((r) => r.offer_id)).toEqual(['a', 'b'])

    let resolve!: (r: CompareResponse) => void
    mocked.compare.mockImplementationOnce(() => new Promise<CompareResponse>((r) => (resolve = r)))
    act(() => result.current.loadMore({ top_n: 2 } as never))
    expect(mocked.compare.mock.calls[1][0]).toMatchObject({ top_n: 2, offset: 2 })
    expect(result.current.loadingMore).toBe(true)
    expect(result.current.status).toBe('success')
    expect(result.current.data?.results).toHaveLength(2) // old rows stay while loading

    await act(async () => resolve(page(['c', 'd', 'b'])))
    expect(result.current.loadingMore).toBe(false)
    // 'b' is repeated by the server: not shown twice
    expect(result.current.data?.results.map((r) => r.offer_id)).toEqual(['a', 'b', 'c', 'd'])
  })

  it('drops a late page when a newer run started', async () => {
    mocked.compare.mockResolvedValueOnce(page(['a', 'b']))
    const { result } = renderHook(() => useComparison())
    await act(async () => result.current.run({} as never))

    let resolveMore!: (r: CompareResponse) => void
    const signals: AbortSignal[] = []
    mocked.compare.mockImplementationOnce((_b, s) => {
      signals.push(s!)
      return new Promise<CompareResponse>((r) => (resolveMore = r))
    })
    act(() => result.current.loadMore({} as never))

    mocked.compare.mockResolvedValueOnce(page(['x', 'y']))
    await act(async () => result.current.run({} as never)) // e.g. a filter changed
    expect(signals[0].aborted).toBe(true)
    expect(result.current.loadingMore).toBe(false)

    await act(async () => resolveMore(page(['c', 'd']))) // the old page arrives late
    expect(result.current.data?.results.map((r) => r.offer_id)).toEqual(['x', 'y'])
  })

  it('ignores loadMore while a run or another page is in flight, and with no data', async () => {
    const { result } = renderHook(() => useComparison())
    act(() => result.current.loadMore({} as never))
    expect(mocked.compare).not.toHaveBeenCalled()

    mocked.compare.mockResolvedValueOnce(page(['a']))
    await act(async () => result.current.run({} as never))
    mocked.compare.mockImplementationOnce((_b, s) => abortable(s))
    act(() => result.current.loadMore({} as never))
    act(() => result.current.loadMore({} as never))
    expect(mocked.compare).toHaveBeenCalledTimes(2)

    mocked.compare.mockImplementationOnce((_b, s) => abortable(s))
    act(() => result.current.run({} as never))
    act(() => result.current.loadMore({} as never))
    expect(mocked.compare).toHaveBeenCalledTimes(3)
  })

  it('a failed page keeps the rows and reports moreError, not a full error', async () => {
    mocked.compare.mockResolvedValueOnce(page(['a']))
    const { result } = renderHook(() => useComparison())
    await act(async () => result.current.run({} as never))
    mocked.compare.mockRejectedValueOnce(new ApiError('down', 0))
    await act(async () => result.current.loadMore({} as never))
    expect(result.current.status).toBe('success')
    expect(result.current.error).toBeNull()
    expect(result.current.moreError?.status).toBe(0)
    expect(result.current.data?.results).toHaveLength(1)
    expect(result.current.loadingMore).toBe(false)
  })

  it('reset drops data and cancels a page in flight', async () => {
    mocked.compare.mockResolvedValueOnce(page(['a']))
    const { result } = renderHook(() => useComparison())
    await act(async () => result.current.run({} as never))
    let resolveMore!: (r: CompareResponse) => void
    mocked.compare.mockImplementationOnce(() => new Promise<CompareResponse>((r) => (resolveMore = r)))
    act(() => result.current.loadMore({} as never))
    act(() => result.current.reset())
    await act(async () => resolveMore(page(['c'])))
    expect(result.current.data).toBeNull()
    expect(result.current.status).toBe('idle')
  })
})

describe('useApiStatus', () => {
  const okHealth: Health = { status: 'ok', catalog_loaded: true, snapshot_date: '2026-09-29', catalog_age_days: 1 }

  it('checking → waking after 4s → ready when health answers', async () => {
    let resolveHealth!: (h: Health) => void
    mocked.health.mockImplementation(() => new Promise<Health>((r) => (resolveHealth = r)))
    mocked.catalogMeta.mockResolvedValue({ attribution: 'x' } as never)
    const { result } = renderHook(() => useApiStatus())
    expect(result.current.status).toBe('checking')
    await act(() => vi.advanceTimersByTimeAsync(3900))
    expect(result.current.status).toBe('checking')
    await act(() => vi.advanceTimersByTimeAsync(200))
    expect(result.current.status).toBe('waking')
    await act(async () => resolveHealth(okHealth))
    expect(result.current.status).toBe('ready')
    expect(result.current.meta).toEqual({ attribution: 'x' })
  })

  it('no-catalog when health says not loaded', async () => {
    mocked.health.mockResolvedValue({ ...okHealth, catalog_loaded: false })
    const { result } = renderHook(() => useApiStatus())
    await act(() => vi.advanceTimersByTimeAsync(0))
    expect(result.current.status).toBe('no-catalog')
  })

  it('unreachable after 75s of failures; retry restarts', async () => {
    mocked.health.mockRejectedValue(new ApiError('down', 0))
    const { result } = renderHook(() => useApiStatus())
    await act(() => vi.advanceTimersByTimeAsync(76_000))
    expect(result.current.status).toBe('unreachable')

    mocked.health.mockResolvedValue({ ...okHealth, catalog_loaded: false })
    act(() => result.current.retry())
    expect(result.current.status).toBe('checking')
    await act(() => vi.advanceTimersByTimeAsync(0))
    expect(result.current.status).toBe('no-catalog')
  })
})
