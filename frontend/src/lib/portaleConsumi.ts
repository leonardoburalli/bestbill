import { parseItalianNumber, type MonthRow } from './consumption'
import { buildMonths, lastCompleteMonth, startFromEnd } from './months'

export type ImportedMonth = {
  month: string // YYYY-MM
  kwh: number
  f1: number | null
  f2: number | null
  f3: number | null
}

export type PortaleConsumiParse = {
  months: ImportedMonth[]
  hasBands: boolean
  warnings: string[]
}

/** Error with an Italian, user-facing message. */
export class PortaleConsumiError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'PortaleConsumiError'
  }
}

export const MAX_FILE_BYTES = 1024 * 1024

const MONTH_ABBR = ['gen', 'feb', 'mar', 'apr', 'mag', 'giu', 'lug', 'ago', 'set', 'ott', 'nov', 'dic']
const BAND_KEYS = ['f1', 'f2', 'f3', 'f4', 'f5', 'f6'] as const
type RowKey = 'unica' | (typeof BAND_KEYS)[number]

const round2 = (n: number) => Math.round(n * 100) / 100

/** Minimal CSV line splitter: `;` separator, optional double quotes ("" escapes). Cells are trimmed. */
function splitLine(line: string): string[] {
  const cells: string[] = []
  let cur = ''
  let inQuotes = false
  for (let i = 0; i < line.length; i++) {
    const c = line[i]
    if (inQuotes) {
      if (c === '"') {
        if (line[i + 1] === '"') {
          cur += '"'
          i++
        } else inQuotes = false
      } else cur += c
    } else if (c === '"') inQuotes = true
    else if (c === ';') {
      cells.push(cur.trim())
      cur = ''
    } else cur += c
  }
  cells.push(cur.trim())
  return cells
}

function parseHeaderMonth(cell: string): string | null {
  const m = /^([A-Za-zÀ-ÿ]{3})\s*-\s*(\d{2})$/.exec(cell.trim())
  if (!m) return null
  const idx = MONTH_ABBR.indexOf(m[1].toLowerCase())
  if (idx < 0) return null
  return `${2000 + Number(m[2])}-${String(idx + 1).padStart(2, '0')}`
}

function rowKey(label: string): RowKey | null {
  const l = label.trim().toLowerCase().replace(/\s+/g, ' ')
  if (l === 'fascia unica') return 'unica'
  return (BAND_KEYS as readonly string[]).includes(l) ? (l as RowKey) : null
}

export function parsePortaleConsumiCsv(text: string): PortaleConsumiParse {
  const lines = text
    .replace(/^\uFEFF/, '')
    .split(/\r\n|\n|\r/)
    .filter((l) => l.trim() !== '')
  if (lines.length < 2) {
    throw new PortaleConsumiError(
      'Il file non sembra un CSV di Portale Consumi: mancano l’intestazione dei mesi o le righe dei consumi.',
    )
  }

  const header = splitLine(lines[0])
  const monthCells = header.slice(1)
  const monthKeys: string[] = []
  for (const cell of monthCells) {
    const key = parseHeaderMonth(cell)
    if (!key) {
      throw new PortaleConsumiError(
        `Intestazione dei mesi non riconosciuta (“${cell}”). Il file deve contenere colonne come “Gen - 26”.`,
      )
    }
    monthKeys.push(key)
  }
  if (monthKeys.length === 0) {
    throw new PortaleConsumiError('Nel file non è stato trovato nessun mese.')
  }
  if (new Set(monthKeys).size !== monthKeys.length) {
    throw new PortaleConsumiError('Il file contiene mesi ripetuti nell’intestazione.')
  }

  const data = new Map<RowKey, (number | null)[]>()
  for (const line of lines.slice(1)) {
    const cells = splitLine(line)
    const key = rowKey(cells[0] ?? '')
    if (!key) continue
    const values = monthKeys.map((_, i) => {
      const raw = (cells[i + 1] ?? '').trim()
      if (raw === '' || raw === '-') return null
      const n = parseItalianNumber(raw)
      if (n === null || n < 0) {
        throw new PortaleConsumiError(`Valore non valido nella riga “${cells[0]}”: “${raw}”.`)
      }
      return n
    })
    data.set(key, values)
  }
  if (data.size === 0) {
    throw new PortaleConsumiError(
      'Nel file non ci sono righe di consumo riconosciute (Fascia unica, F1, F2, F3).',
    )
  }

  const warnings: string[] = []
  const val = (k: RowKey, i: number) => data.get(k)?.[i] ?? 0
  const has3 = data.has('f1') && data.has('f2') && data.has('f3')
  const extraNonZero = (['f4', 'f5', 'f6'] as const).some((k) => data.get(k)?.some((v) => (v ?? 0) > 0))
  const unicaNonZero = data.get('unica')?.some((v) => (v ?? 0) > 0) ?? false

  const months: ImportedMonth[] = monthKeys.map((month, i) => {
    let total = 0
    for (const k of ['unica', ...BAND_KEYS] as RowKey[]) total += val(k, i)
    return {
      month,
      kwh: round2(total),
      f1: data.has('f1') ? val('f1', i) : null,
      f2: data.has('f2') ? val('f2', i) : null,
      f3: data.has('f3') ? val('f3', i) : null,
    }
  })
  months.sort((a, b) => a.month.localeCompare(b.month))

  if (extraNonZero) {
    warnings.push(
      'Il file contiene consumi nelle fasce F4–F6: sono stati sommati ai kWh totali e il dettaglio per fasce F1–F3 è stato disattivato.',
    )
  } else if (unicaNonZero && has3 && months.some((m) => (m.f1 ?? 0) + (m.f2 ?? 0) + (m.f3 ?? 0) > 0)) {
    warnings.push(
      'Il file contiene sia “Fascia unica” sia F1–F3 in mesi diversi: sono stati usati i kWh totali mensili, senza dettaglio per fasce.',
    )
  }
  const hasBands = has3 && !unicaNonZero && !extraNonZero

  return { months, hasBands, warnings }
}

function readBuffer(file: File): Promise<ArrayBuffer> {
  if (typeof file.arrayBuffer === 'function') return file.arrayBuffer()
  return new Promise((resolve, reject) => {
    const fr = new FileReader()
    fr.onload = () => resolve(fr.result as ArrayBuffer)
    fr.onerror = () => reject(new PortaleConsumiError('Impossibile leggere il file.'))
    fr.readAsArrayBuffer(file)
  })
}

export async function readPortaleConsumiFile(file: File): Promise<PortaleConsumiParse> {
  if (file.size > MAX_FILE_BYTES) {
    throw new PortaleConsumiError('Il file è troppo grande (massimo 1 MB).')
  }
  const buf = await readBuffer(file)
  let text = new TextDecoder('utf-8').decode(buf)
  if (text.includes('\uFFFD')) text = new TextDecoder('windows-1252').decode(buf)
  return parsePortaleConsumiCsv(text)
}

/** Latest imported month that is ≤ the last complete month, or null if none. */
export function suggestEndMonth(months: ImportedMonth[], today: Date = new Date()): string | null {
  const cap = lastCompleteMonth(today)
  let best: string | null = null
  for (const m of months) if (m.month <= cap && (best === null || m.month > best)) best = m.month
  return best
}

export function applyImport(
  imported: ImportedMonth[],
  end: string,
  useBands: boolean,
): { rows: MonthRow[]; filled: number; missing: string[] } {
  const byMonth = new Map(imported.map((m) => [m.month, m]))
  const rows: MonthRow[] = []
  const missing: string[] = []
  let filled = 0
  for (const month of buildMonths(startFromEnd(end))) {
    const m = byMonth.get(month)
    if (!m) {
      missing.push(month)
      rows.push({ month, kwh: null, f1: null, f2: null, f3: null })
      continue
    }
    filled++
    rows.push({
      month,
      kwh: m.kwh,
      f1: useBands ? m.f1 : null,
      f2: useBands ? m.f2 : null,
      f3: useBands ? m.f3 : null,
    })
  }
  return { rows, filled, missing }
}

export type PortaleFile = { name: string; months: ImportedMonth[]; hasBands: boolean; warnings: string[] }
export type MergedImport = {
  months: ImportedMonth[]
  hasBands: boolean
  warnings: string[]
  files: { name: string; first: string | null; last: string | null; count: number }[]
}

export async function readPortaleFile(file: File): Promise<PortaleFile> {
  try {
    const parsed = await readPortaleConsumiFile(file)
    return { name: file.name, ...parsed }
  } catch (e) {
    if (e instanceof PortaleConsumiError) {
      throw new PortaleConsumiError(`${file.name}: ${e.message}`)
    }
    throw e
  }
}

const EPS = 0.01
const close = (a: number | null, b: number | null) =>
  a === null || b === null ? a === b : Math.abs(a - b) <= EPS
const sameMonth = (a: ImportedMonth, b: ImportedMonth) =>
  a.month === b.month && close(a.kwh, b.kwh) && close(a.f1, b.f1) && close(a.f2, b.f2) && close(a.f3, b.f3)
const hasMonthBands = (m: ImportedMonth) => m.f1 !== null && m.f2 !== null && m.f3 !== null

export function mergePortaleFiles(files: PortaleFile[]): MergedImport {
  const warnings: string[] = []
  const kept: PortaleFile[] = []
  for (const f of files) {
    const dup = kept.find(
      (k) =>
        k.name === f.name &&
        k.months.length === f.months.length &&
        k.months.every((m, i) => sameMonth(m, f.months[i])),
    )
    if (dup) {
      warnings.push(`Il file “${f.name}” è stato caricato due volte: ignoro il duplicato.`)
      continue
    }
    kept.push(f)
    for (const w of f.warnings) warnings.push(`${f.name}: ${w}`)
  }

  const byMonth = new Map<string, { m: ImportedMonth; file: string }>()
  for (const f of kept) {
    for (const raw of f.months) {
      const m: ImportedMonth = f.hasBands ? { ...raw } : { ...raw, f1: null, f2: null, f3: null }
      const prev = byMonth.get(m.month)
      if (!prev) {
        byMonth.set(m.month, { m, file: f.name })
        continue
      }
      if (sameMonth(prev.m, m)) continue
      const winner = m.kwh > prev.m.kwh ? { m, file: f.name } : prev
      warnings.push(
        `Il mese ${m.month} è presente con valori diversi in “${prev.file}” e “${f.name}”: uso il valore più alto (${winner.m.kwh} kWh, da “${winner.file}”).`,
      )
      byMonth.set(m.month, winner)
    }
  }

  const months = [...byMonth.values()].map((v) => v.m).sort((a, b) => a.month.localeCompare(b.month))
  let hasBands = months.length > 0 && months.every(hasMonthBands)
  if (!hasBands && months.some(hasMonthBands)) {
    warnings.push('Alcuni mesi non hanno la ripartizione per fasce: userò solo i totali.')
  }
  if (!hasBands) for (const m of months) m.f1 = m.f2 = m.f3 = null
  hasBands = hasBands && months.length > 0

  return {
    months,
    hasBands,
    warnings,
    files: kept.map((f) => ({
      name: f.name,
      first: f.months.length ? f.months[0].month : null,
      last: f.months.length ? f.months[f.months.length - 1].month : null,
      count: f.months.length,
    })),
  }
}
