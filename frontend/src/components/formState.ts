/**
 * Stato del modulo "consumi" e regole di controllo lato browser.
 * I numeri restano testo finché non vengono inviati: così si può scrivere "1.234,5"
 * senza che il campo si "corregga" da solo mentre si digita.
 */
import { useCallback, useMemo, useState } from 'react'
import type { FieldError } from '../api'
import { POWER_MAX, parseItalianNumber, toRequestMonths, validateRows } from '../lib/consumption'
import type { MonthRow } from '../lib/consumption'
import { buildMonths, defaultStartMonth } from '../lib/months'
import type { CompareFilters, CompareRequest, Comune, Residency, Scenario } from '../types'

export type Cell = { kwh: string; f1: string; f2: string; f3: string }
export type CellField = keyof Cell

export interface FormState {
  start: string
  cells: Cell[]
  useBands: boolean
  residency: Residency
  power: string
}

const emptyCell = (): Cell => ({ kwh: '', f1: '', f2: '', f3: '' })

export function initialForm(): FormState {
  return {
    start: defaultStartMonth(),
    cells: Array.from({ length: 12 }, emptyCell),
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
  const [note, setNote] = useState<string | null>(null)

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

  /** Carica 12 mesi provenienti da esempio o da Excel. */
  const applyRows = useCallback(
    (data: { start: string; rows: MonthRow[]; hasBands: boolean }, why: string) => {
      setForm((f) => ({
        ...f,
        start: data.start || f.start,
        useBands: data.hasBands,
        cells: Array.from({ length: 12 }, (_, i) => {
          const r = data.rows[i]
          return r
            ? { kwh: numToText(r.kwh), f1: numToText(r.f1), f2: numToText(r.f2), f3: numToText(r.f3) }
            : emptyCell()
        }),
      }))
      setServerErrors([])
      setNote(why)
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
    applyRows,
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
