import { api, ApiError } from './api'

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

let fetchMock: ReturnType<typeof vi.fn>
beforeEach(() => {
  fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
})
afterEach(() => vi.unstubAllGlobals())

describe('api', () => {
  it('GET sends no Content-Type', async () => {
    fetchMock.mockResolvedValue(json({ status: 'ok' }))
    await api.health()
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/health')
    expect(init.headers).toBeUndefined()
    expect(init.method).toBeUndefined()
  })
  it('comuni encodes query', async () => {
    fetchMock.mockResolvedValue(json([]))
    await api.comuni('San Donà')
    expect(fetchMock.mock.calls[0][0]).toBe('/api/comuni?q=San%20Don%C3%A0')
  })
  it('POST compare sends JSON content type', async () => {
    fetchMock.mockResolvedValue(json({}))
    await api.compare({ consumption: [], residency: 'resident' })
    const init = fetchMock.mock.calls[0][1]
    expect(init.method).toBe('POST')
    expect(init.headers).toEqual({ 'Content-Type': 'application/json' })
  })
  it('422 → fieldErrors', async () => {
    fetchMock.mockResolvedValue(json({ detail: [{ field: 'consumption.3.kwh', message: 'Troppo alto' }] }, 422))
    const err = await api.compare({} as never).catch((e) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err.status).toBe(422)
    expect(err.fieldErrors).toEqual([{ field: 'consumption.3.kwh', message: 'Troppo alto' }])
    expect(err.message).toBe('Troppo alto')
  })
  it('string detail and Italian fallbacks', async () => {
    fetchMock.mockResolvedValueOnce(json({ detail: 'Il file supera i 2 MB.' }, 413))
    expect((await api.sample().catch((e) => e)).message).toBe('Il file supera i 2 MB.')
    fetchMock.mockResolvedValueOnce(new Response('<html>', { status: 429 }))
    const e429 = await api.sample().catch((e) => e)
    expect(e429.status).toBe(429)
    expect(e429.message).toMatch(/Troppe richieste/)
  })
  it('network failure → status 0', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))
    const err = await api.health().catch((e) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err.status).toBe(0)
  })
  it('AbortError propagates unwrapped', async () => {
    const abort = new DOMException('Aborted', 'AbortError')
    fetchMock.mockRejectedValue(abort)
    await expect(api.health()).rejects.toBe(abort)
  })
})
