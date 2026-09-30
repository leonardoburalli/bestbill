/**
 * Stato del modulo "consumi" e regole di controllo lato browser.
 * I numeri restano testo finché non vengono inviati: così si può scrivere "1.234,5"
 * senza che il campo si "corregga" da solo mentre si digita.
 */
import { useCallback, useMemo, useState } from 'react'
import type { FieldError } from '../api'
import { POWER_MAX, parseItalianNumber, toRequestMonths, validateRows } from '../lib/consumption'
import type { MonthRow } from '../lib/consumption'
import { buildMonths, endFromStart, lastCompleteMonth, startFromEnd } from '../lib/months'
import { applyImport, suggestEndMonth } from '../lib/portaleConsumi'
import type { ImportedMonth, parsePortaleConsumiCsv } from '../lib/portaleConsumi'
import type { CompareFilters, CompareRequest, Comune, Residency, Scenario } from '../types'

export type Cell = { kwh: string; f1: string; f2: string; f3: string }
export type CellField = keyof Cell

export interface FormState {
  /** Primo mese (YYYY-MM) dei 12 mesi di riferimento. L'ultimo è sempre start + 11. */
  start: string
  cells: Cell[]
  /** Valori dei mesi usciti dal periodo: tornano se si riporta il periodo indietro. */
  stash: Record<string, Cell>
  /** Mesi letti da Portale Consumi (tutti, anche fuori dai 12 mostrati). */
  imported: ImportedMonth[] | null
  useBands: boolean
  residency: Residency
  power: string
}

const emptyCell = (): Cell => ({ kwh: '', f1: '', f2: '', f3: '' })
const isEmptyCell = (c: Cell) => !c.kwh.trim() && !c.f1.trim() && !c.f2.trim() && !c.f3.trim()
const cellFromRow = (r: MonthRow): Cell => ({
  kwh: numToText(r.kwh),
  f1: numToText(r.f1),
  f2: numToText(r.f2),
  f3: numToText(r.f3),
})

/** Riepilogo dell'ultima importazione da Portale Consumi, mostrato sopra la tabella. */
export interface ImportReport {
  fileName: string
  /** Mesi presenti nel file. */
  totalMonths: number
  filled: number
  /** Mesi (YYYY-MM) dei 12 scelti che non sono nel file. */
  missing: string[]
  warnings: string[]
  first: string
  last: string
}

export function initialForm(): FormState {
  return {
    start: startFromEnd(lastCompleteMonth()),
    cells: Array.from({ length: 12 }, emptyCell),
    stash: {},
    imported: null,
    useBands: false,
    residency: 'resident',
    power: '3',
  }
}

/** Numero → testo con virgola decimale, senza separatore delle migliaia. */
export function numToText(n: number | null): string {
  if (n === null || Number.isNaN(n)) return ''
  return String(Math.round(n * 100) / 100).replace('.', ',')
}

export function rowsOf(form: FormState): MonthRow[] {
  const months = buildMonths(form.start)
  return form.cells.map((c, i) => ({
    month: months[i],
    kwh: parseItalianNumber(c.kwh),
    f1: parseItalianNumber(c.f1),
    f2: parseItalianNumber(c.f2),
    f3: parseItalianNumber(c.f3),
  }))
}

export interface RowFeedback {
  kwh?: string
  bands?: string
  /** Somma F1+F2+F3 quando tutte e tre sono leggibili. */
  bandSum: number | null
  bandsOk: boolean
  kwhTouched: boolean
  bandsTouched: boolean
}

export interface FormCheck {
  ok: boolean
  rows: RowFeedback[]
  totalKwh: number
  filled: number
  power?: string
}

const NOT_A_NUMBER = 'Scrivi un numero, per esempio 180 oppure 180,5.'

export function checkForm(form: FormState): FormCheck {
  const rows = rowsOf(form)
  const v = validateRows(rows, form.useBands)
  const fb: RowFeedback[] = form.cells.map((c, i) => {
    const r = rows[i]
    const kwhBad = c.kwh.trim() !== '' && r.kwh === null
    const bandBad = (['f1', 'f2', 'f3'] as const).some((k) => c[k].trim() !== '' && r[k] === null)
    const issue = (f: 'kwh' | 'bands') => v.issues.find((x) => x.index === i && x.field === f)?.message
    const bandSum =
      r.f1 !== null && r.f2 !== null && r.f3 !== null ? r.f1 + r.f2 + r.f3 : null
    const bands = form.useBands ? (bandBad ? NOT_A_NUMBER : issue('bands')) : undefined
    return {
      kwh: kwhBad ? NOT_A_NUMBER : issue('kwh'),
      bands,
      bandSum,
      bandsOk: form.useBands && bandSum !== null && !bands && !bandBad,
      kwhTouched: c.kwh.trim() !== '',
      bandsTouched: c.f1.trim() !== '' || c.f2.trim() !== '' || c.f3.trim() !== '',
    }
  })
  const p = parseItalianNumber(form.power)
  let power: string | undefined
  if (p === null) power = 'Indica la potenza in kW, per esempio 3 oppure 4,5.'
  else if (p <= 0 || p > POWER_MAX) power = `La potenza deve essere maggiore di 0 e al massimo ${POWER_MAX} kW.`
  const ok = fb.every((f) => !f.kwh && !f.bands) && !power
  return {
    ok,
    rows: fb,
    totalKwh: v.totalKwh,
    filled: rows.filter((r) => r.kwh !== null).length,
    power,
  }
}

export function comuneLabel(c: Comune): string {
  return `${c.nome} (${c.sigla_provincia})`
}

export function buildRequest(
  form: FormState,
  comune: Comune | null,
  scenario: Scenario,
  filters: CompareFilters,
): CompareRequest {
  const f: CompareFilters = {}
  if (filters.price_type) f.price_type = filters.price_type
  if (filters.source) f.source = filters.source
  return {
    consumption: toRequestMonths(rowsOf(form), form.useBands),
    residency: form.residency,
    istat_comune: comune?.codice ?? null,
    committed_power_kw: parseItalianNumber(form.power) ?? 3,
    scenario,
    filters: f,
    top_n: 50,
  }
}

/* ── Errori 422 del server, riportati sui campi giusti ─────────────────── */

export interface ServerErrorMap {
  rows: Record<number, { kwh?: string; bands?: string; general?: string }>
  comune?: string
  power?: string
  general: string[]
}

const ROW_RE = /^consumption\[(\d+)\](?:\.(\w+))?$/

export function mapServerErrors(errors: FieldError[]): ServerErrorMap {
  const out: ServerErrorMap = { rows: {}, general: [] }
  for (const e of errors) {
    const m = ROW_RE.exec(e.field)
    if (m) {
      const i = Number(m[1])
      const row = (out.rows[i] ??= {})
      if (m[2] === 'kwh') row.kwh = e.message
      else if (m[2] === 'f1' || m[2] === 'f2' || m[2] === 'f3') row.bands = e.message
      else row.general = e.message
    } else if (e.field === 'istat_comune') out.comune = e.message
    else if (e.field === 'committed_power_kw') out.power = e.message
    else out.general.push(e.message)
  }
  return out
}

/** Campi del server che richiedono di tornare al passo 1. */
export const isInputField = (field: string) =>
  field.startsWith('consumption') ||
  field === 'istat_comune' ||
  field === 'committed_power_kw' ||
  field === 'residency'

/* ── Hook con lo stato del modulo (vive in App, così "Modifica" conserva tutto) ── */

export function useConsumptionForm() {
  const [form, setForm] = useState<FormState>(initialForm)
  const [serverErrors, setServerErrors] = useState<FieldError[]>([])
  const [attempted, setAttempted] = useState(false)
  const [note, setNoteRaw] = useState<string | null>(null)
  const [report, setReport] = useState<ImportReport | null>(null)

  /** Un solo messaggio alla volta sopra la tabella. */
  const setNote = useCallback((n: string | null) => {
    setNoteRaw(n)
    if (n) setReport(null)
  }, [])

  const patch = useCallback((p: Partial<FormState>) => {
    setForm((f) => ({ ...f, ...p }))
    setServerErrors([])
  }, [])

  const setCells = useCallback((fn: (cells: Cell[]) => Cell[]) => {
    setForm((f) => ({ ...f, cells: fn(f.cells) }))
    setServerErrors([])
  }, [])

  const setCell = useCallback(
    (i: number, field: CellField, value: string) =>
      setCells((cells) => cells.map((c, j) => (j === i ? { ...c, [field]: value } : c))),
    [setCells],
  )

  /**
   * Sposta il periodo. I valori si tengono per mese di calendario: i mesi che restano nel
   * periodo conservano ciò che c'è scritto, i mesi nuovi si riempiono dal file importato (se c'è)
   * oppure restano vuoti. I mesi che escono vengono messi da parte e tornano se si torna indietro.
   */
  const setPeriod = useCallback((start: string) => {
    setForm((f) => {
      if (start === f.start) return f
      const kept: Record<string, Cell> = { ...f.stash }
      buildMonths(f.start).forEach((m, i) => {
        if (!isEmptyCell(f.cells[i])) kept[m] = f.cells[i]
        else delete kept[m]
      })
      const fromFile = f.imported ? applyImport(f.imported, endFromStart(start), f.useBands).rows : []
      const byMonth = new Map(fromFile.map((r) => [r.month, r]))
      const months = buildMonths(start)
      const cells = months.map((m) => {
        if (kept[m]) return kept[m]
        const r = byMonth.get(m)
        return r && r.kwh !== null ? cellFromRow(r) : emptyCell()
      })
      const stash = { ...kept }
      months.forEach((m) => delete stash[m])
      return { ...f, start, cells, stash }
    })
    setServerErrors([])
  }, [])

  /** Carica 12 mesi provenienti dall'esempio. */
  const applyRows = useCallback(
    (data: { start: string; rows: MonthRow[]; hasBands: boolean }, why: string) => {
      setForm((f) => ({
        ...f,
        start: data.start || f.start,
        useBands: data.hasBands,
        stash: {},
        imported: null,
        cells: Array.from({ length: 12 }, (_, i) => {
          const r = data.rows[i]
          return r ? cellFromRow(r) : emptyCell()
        }),
      }))
      setServerErrors([])
      setNote(why)
    },
    [setNote],
  )

  /** Dopo un incolla: i valori sono a mano, non più quelli del file. */
  const forgetImport = useCallback(() => {
    setForm((f) => ({ ...f, imported: null, stash: {} }))
    setReport(null)
  }, [])

  /** Importa dal file di Portale Consumi. Restituisce un messaggio se non c'è nulla di utilizzabile. */
  const importPortale = useCallback(
    (parsed: ReturnType<typeof parsePortaleConsumiCsv>, fileName: string): string | null => {
      const end = suggestEndMonth(parsed.months)
      if (!end) {
        return 'Nel file ci sono solo mesi non ancora conclusi. Servono consumi di mesi già passati.'
      }
      const res = applyImport(parsed.months, end, parsed.hasBands)
      setForm((f) => ({
        ...f,
        start: startFromEnd(end),
        useBands: parsed.hasBands,
        stash: {},
        imported: parsed.months,
        cells: res.rows.map((r) => (r.kwh !== null ? cellFromRow(r) : emptyCell())),
      }))
      setServerErrors([])
      setNoteRaw(null)
      setReport({
        fileName,
        totalMonths: parsed.months.length,
        filled: res.filled,
        missing: res.missing,
        warnings: parsed.warnings,
        first: parsed.months[0].month,
        last: parsed.months[parsed.months.length - 1].month,
      })
      return null
    },
    [],
  )

  const check = useMemo(() => checkForm(form), [form])
  const mapped = useMemo(() => mapServerErrors(serverErrors), [serverErrors])

  return {
    form,
    patch,
    setCell,
    setCells,
    setPeriod,
    applyRows,
    importPortale,
    forgetImport,
    report,
    check,
    serverErrors,
    setServerErrors,
    mapped,
    attempted,
    setAttempted,
    note,
    setNote,
  }
}

export type ConsumptionForm = ReturnType<typeof useConsumptionForm>
