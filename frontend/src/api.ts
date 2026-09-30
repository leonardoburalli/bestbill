import type {
  CatalogMeta,
  Comune,
  CompareRequest,
  CompareResponse,
  Health,
  SampleHousehold,
} from './types'

/** Same-origin by default (Vercel rewrite in production, Vite proxy in dev). */
export const API_BASE: string = import.meta.env.VITE_API_BASE ?? ''

export interface FieldError {
  field: string
  message: string
}

export class ApiError extends Error {
  status: number
  fieldErrors: FieldError[]

  constructor(message: string, status: number, fieldErrors: FieldError[] = []) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.fieldErrors = fieldErrors
  }
}

function fallbackMessage(status: number): string {
  switch (status) {
    case 0:
      return 'Impossibile raggiungere il server. Controlla la connessione e riprova.'
    case 413:
      return 'Il file o i dati inviati sono troppo grandi.'
    case 422:
      return 'I dati inseriti non sono validi.'
    case 429:
      return 'Troppe richieste in poco tempo. Attendi un minuto e riprova.'
    case 503:
      return 'Il catalogo delle offerte non è ancora disponibile. Riprova tra poco.'
    default:
      return status >= 500
        ? `Errore del server (${status}). Riprova tra poco.`
        : `Richiesta non riuscita (${status}).`
  }
}

function isFieldError(e: unknown): e is FieldError {
  return (
    typeof e === 'object' &&
    e !== null &&
    typeof (e as FieldError).field === 'string' &&
    typeof (e as FieldError).message === 'string'
  )
}

async function toApiError(res: Response): Promise<ApiError> {
  let body: unknown = null
  try {
    body = await res.json()
  } catch {
    /* non-JSON error body */
  }
  const detail = (body as { detail?: unknown } | null)?.detail
  if (Array.isArray(detail)) {
    const fieldErrors = detail.filter(isFieldError)
    const message = fieldErrors.length
      ? fieldErrors.map((e) => e.message).join(' ')
      : fallbackMessage(res.status)
    return new ApiError(message, res.status, fieldErrors)
  }
  if (typeof detail === 'string' && detail) return new ApiError(detail, res.status)
  return new ApiError(fallbackMessage(res.status), res.status)
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, init)
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') throw e
    if (e instanceof Error && e.name === 'AbortError') throw e
    throw new ApiError(fallbackMessage(0), 0)
  }
  if (!res.ok) throw await toApiError(res)
  try {
    return (await res.json()) as T
  } catch (e) {
    if (e instanceof Error && e.name === 'AbortError') throw e
    throw new ApiError('Risposta del server non valida.', res.status)
  }
}

export const api = {
  health: (signal?: AbortSignal) => request<Health>('/api/health', { signal }),
  catalogMeta: (signal?: AbortSignal) =>
    request<CatalogMeta>('/api/catalog/meta', { signal }),
  sample: (signal?: AbortSignal) => request<SampleHousehold>('/api/sample', { signal }),
  comuni: (q: string, signal?: AbortSignal) =>
    request<Comune[]>(`/api/comuni?q=${encodeURIComponent(q)}`, { signal }),
  compare: (body: CompareRequest, signal?: AbortSignal) =>
    request<CompareResponse>('/api/compare', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    }),
}
