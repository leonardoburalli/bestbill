import type { MonthInput, SampleMonth } from '../types'
import { buildMonths } from './months'

/** Mirrors schemas.py Kwh: 0 <= kwh <= 100_000. */
export const KWH_MIN = 0
export const KWH_MAX = 100_000
/** Mirrors core/models.py MonthlyConsumption: band sum within 0.5% of kwh. */
export const BAND_TOLERANCE = 0.005
/** Mirrors schemas.py BAND_TOLERANCE_MESSAGE. */
export const BAND_TOLERANCE_MESSAGE =
  'La somma di F1, F2 e F3 deve coincidere con i kWh totali del mese (tolleranza 0,5%).'
/** Mirrors schemas.py CompareRequest.committed_power_kw: 0 < kw <= 30. */
export const POWER_MIN_EXCLUSIVE = 0
export const POWER_MAX = 30

export type MonthRow = {
  month: string
  kwh: number | null
  f1: number | null
  f2: number | null
  f3: number | null
}

export function emptyRows(start: string): MonthRow[] {
  return buildMonths(start).map((month) => ({ month, kwh: null, f1: null, f2: null, f3: null }))
}

export function reanchorRows(rows: MonthRow[], start: string): MonthRow[] {
  const months = buildMonths(start)
  return months.map((month, i) => {
    const r = rows[i]
    return r ? { ...r, month } : { month, kwh: null, f1: null, f2: null, f3: null }
  })
}

export function rowsFromApi(months: SampleMonth[] | MonthInput[]): {
  start: string
  rows: MonthRow[]
  hasBands: boolean
} {
  const sorted = [...(months as MonthInput[])].sort((a, b) => a.month.localeCompare(b.month))
  const rows: MonthRow[] = sorted.map((m) => ({
    month: m.month,
    kwh: m.kwh,
    f1: m.f1 ?? null,
    f2: m.f2 ?? null,
    f3: m.f3 ?? null,
  }))
  const hasBands = rows.length > 0 && rows.every((r) => r.f1 !== null && r.f2 !== null && r.f3 !== null)
  return { start: rows[0]?.month ?? '', rows, hasBands }
}

/** "1.234,5" → 1234.5, "180" → 180, "" → null, invalid → null. */
export function parseItalianNumber(s: string): number | null {
  let t = s.trim().replace(/\s/g, '')
  if (!t) return null
  if (t.includes(',')) {
    // comma is decimal separator; dots are thousands separators
    if (!/^-?\d{1,3}(\.\d{3})*(,\d+)?$|^-?\d+(,\d+)?$/.test(t)) return null
    t = t.replace(/\./g, '').replace(',', '.')
  } else if (t.includes('.')) {
    // dot only: thousands grouping ("1.234", "1.234.567") else plain decimal ("1.5")
    if (/^-?\d{1,3}(\.\d{3})+$/.test(t)) t = t.replace(/\./g, '')
    else if (!/^-?\d+\.\d+$/.test(t)) return null
  } else if (!/^-?\d+$/.test(t)) {
    return null
  }
  const n = Number(t)
  return Number.isFinite(n) ? n : null
}

/** Split on newline/tab/semicolon/whitespace; keeps only valid numbers. */
export function parsePastedValues(text: string): number[] {
  return text
    .split(/[\n\r\t;\s]+/)
    .map((p) => parseItalianNumber(p))
    .filter((n): n is number => n !== null)
}

export type RowIssue = { index: number; field: 'kwh' | 'bands'; message: string }

export function validateRows(
  rows: MonthRow[],
  useBands: boolean,
): { ok: boolean; issues: RowIssue[]; totalKwh: number } {
  const issues: RowIssue[] = []
  let totalKwh = 0
  rows.forEach((r, index) => {
    if (r.kwh === null || Number.isNaN(r.kwh)) {
      issues.push({ index, field: 'kwh', message: 'Inserisci i kWh del mese.' })
      return
    }
    if (r.kwh < KWH_MIN || r.kwh > KWH_MAX) {
      issues.push({
        index,
        field: 'kwh',
        message: `I kWh devono essere tra 0 e ${KWH_MAX.toLocaleString('it-IT')}.`,
      })
      return
    }
    totalKwh += r.kwh
    if (!useBands) return
    const bands = [r.f1, r.f2, r.f3]
    if (bands.some((b) => b === null)) {
      issues.push({
        index,
        field: 'bands',
        message: 'Indica tutte e tre le fasce F1, F2 e F3 per ogni mese.',
      })
      return
    }
    const [f1, f2, f3] = bands as number[]
    if ([f1, f2, f3].some((b) => b < KWH_MIN || b > KWH_MAX)) {
      issues.push({
        index,
        field: 'bands',
        message: `Le fasce devono essere tra 0 e ${KWH_MAX.toLocaleString('it-IT')} kWh.`,
      })
      return
    }
    const tolerance = Math.max(BAND_TOLERANCE * r.kwh, 1e-9)
    if (Math.abs(f1 + f2 + f3 - r.kwh) > tolerance) {
      issues.push({ index, field: 'bands', message: BAND_TOLERANCE_MESSAGE })
    }
  })
  return { ok: issues.length === 0, issues, totalKwh }
}

/** Bands are sent for all months or none (server rejects mixed requests). */
export function toRequestMonths(rows: MonthRow[], useBands: boolean): MonthInput[] {
  return rows.map((r) => {
    const base: MonthInput = { month: r.month, kwh: r.kwh ?? 0 }
    return useBands ? { ...base, f1: r.f1 ?? 0, f2: r.f2 ?? 0, f3: r.f3 ?? 0 } : base
  })
}
