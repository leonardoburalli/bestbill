const eur = new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', useGrouping: 'always', minimumFractionDigits: 2, maximumFractionDigits: 2 })
const eurCompact = new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', useGrouping: 'always', minimumFractionDigits: 0, maximumFractionDigits: 0 })
const perKwh = new Intl.NumberFormat('it-IT', { minimumFractionDigits: 4, maximumFractionDigits: 4 })
const kwh = new Intl.NumberFormat('it-IT', { maximumFractionDigits: 0, useGrouping: 'always' })

const MONTHS = ['gen', 'feb', 'mar', 'apr', 'mag', 'giu', 'lug', 'ago', 'set', 'ott', 'nov', 'dic']

export const formatEur = (n: number) => eur.format(n)
export const formatEurCompact = (n: number) => eurCompact.format(n)
export const formatEurPerKwh = (n: number) => `${perKwh.format(n)} €/kWh`
/** Spread/price number with sign handling: "PUN + 0,0120" or "PUN − 0,0010" for a negative spread. */
const priceNumber = (n: number, kind: 'fixed' | 'pun_spread' | null | undefined) =>
  kind === 'pun_spread' ? `PUN ${n < 0 ? '−' : '+'} ${perKwh.format(Math.abs(n))}` : perKwh.format(n)
/** Advertised energy price: "0,1604 €/kWh" (fixed) or "PUN + 0,0120 €/kWh" (spread over PUN).
 *  "—" when the API did not send it (older API version). */
export const formatEnergyPrice = (n: number | null | undefined, kind: 'fixed' | 'pun_spread' | null | undefined) =>
  typeof n !== 'number' || !Number.isFinite(n) ? '—' : `${priceNumber(n, kind)} €/kWh`

type EnergyPriceLike = {
  energy_price_eur_kwh?: number | null
  energy_price_kind?: 'fixed' | 'pun_spread' | null
  energy_price_after_discounts_eur_kwh?: number | null
  energy_discount_pct?: number | null
}

export interface EnergyPriceView {
  /** What to show as the price: after unconditional energy discounts when known. "0,1455 €/kWh" / "PUN + 0,0154 €/kWh" */
  main: string
  /** Only when a discount applies: "listino 0,2079 · sconto 30% incluso" (no unit, it is already on the line above). */
  note: string | null
}

const pctFmt = new Intl.NumberFormat('it-IT', { maximumFractionDigits: 1 })

/** Energy price for display. Uses the after-discount price when the API sends it (falls back to the listed
 *  price otherwise) and, if a discount applies, a short note with the list price and the discount. */
export function energyPriceView(item: EnergyPriceLike): EnergyPriceView {
  const kind = item.energy_price_kind
  const listed = item.energy_price_eur_kwh
  const after = item.energy_price_after_discounts_eur_kwh
  const hasListed = typeof listed === 'number' && Number.isFinite(listed)
  const hasAfter = typeof after === 'number' && Number.isFinite(after)
  if (!hasListed) return { main: formatEnergyPrice(hasAfter ? after : null, kind), note: null }
  if (!hasAfter || after >= listed) return { main: formatEnergyPrice(listed, kind), note: null }
  const pct =
    typeof item.energy_discount_pct === 'number' && item.energy_discount_pct > 0
      ? item.energy_discount_pct
      : listed !== 0
        ? Math.round((1 - after / listed) * 1000) / 10
        : 0
  if (!(pct > 0)) return { main: formatEnergyPrice(after, kind), note: null }
  return {
    main: formatEnergyPrice(after, kind),
    note: `listino ${priceNumber(listed, kind)} · sconto ${pctFmt.format(pct)}% incluso`,
  }
}
/** One-line version for running text: "0,1455 €/kWh (listino 0,2079 · sconto 30% incluso)". */
export function energyPriceText(item: EnergyPriceLike): string {
  const v = energyPriceView(item)
  return v.note ? `${v.main} (${v.note})` : v.main
}
/** Same as above without the unit and without a note: CSV cells, "0,1455" / "PUN + 0,0154". */
export function energyPriceCsv(n: number | null | undefined, kind: 'fixed' | 'pun_spread' | null | undefined): string | null {
  return typeof n !== 'number' || !Number.isFinite(n) ? null : priceNumber(n, kind)
}
/** Shown next to the all-in average so it is not compared with the advertised price. */
export const ALL_IN_HINT =
  'Costo totale diviso per i kWh: include quota fissa (CCV), dispacciamento e altri costi. Per questo è più alto del prezzo pubblicizzato.'
/** Fixed selling fee (CCV): "120,00 €/anno". Zero is shown as "0,00 €/anno". */
export const formatEurPerYear = (n: number) => `${eur.format(n)}/anno`
export const formatEurPerMonth = (n: number) => `${eur.format(n)}/mese`
export const formatKwh = (n: number) => `${kwh.format(n)} kWh`

/** "2026-09-29" → "29 set 2026" (local date, no UTC shift). */
export function formatDate(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso)
  if (!m) return iso
  return `${Number(m[3])} ${MONTHS[Number(m[2]) - 1]} ${m[1]}`
}

export type DurationInfo =
  | { kind: 'months'; months: number }
  | { kind: 'open' }
  | { kind: 'unknown' }

type DurationLike = {
  price_type?: 'fixed' | 'variable' | null
  duration_months?: number | null
  duration_open_ended?: boolean | null
}

/** Reads the duration fields defensively: an older API may omit them, which means "unknown". */
export function durationInfo(item: DurationLike): DurationInfo {
  if (item.duration_open_ended === true) return { kind: 'open' }
  const m = item.duration_months
  if (typeof m === 'number' && Number.isFinite(m) && m > 0) return { kind: 'months', months: Math.round(m) }
  return { kind: 'unknown' }
}

const monthsLabel = (n: number) => `${n} ${n === 1 ? 'mese' : 'mesi'}`

/** Full wording: "Prezzo bloccato 24 mesi" (fixed), "Condizioni garantite 24 mesi" (variable),
 *  "Durata non specificata" (no fixed term declared, or not provided). */
export function formatDuration(item: DurationLike): string {
  const d = durationInfo(item)
  if (d.kind === 'open') return 'Durata non specificata'
  if (d.kind === 'unknown') return 'Durata non specificata'
  return `${item.price_type === 'fixed' ? 'Prezzo bloccato' : 'Condizioni garantite'} ${monthsLabel(d.months)}`
}

/** Short wording for tight spaces: "24 mesi", "Non specificata", "—". */
export function formatDurationShort(item: DurationLike): string {
  const d = durationInfo(item)
  if (d.kind === 'open') return 'Non specificata'
  if (d.kind === 'unknown') return '—'
  return monthsLabel(d.months)
}

/** CSV value: months as a number, otherwise "non specificata". */
export function durationCsvValue(item: DurationLike): number | string {
  const d = durationInfo(item)
  return d.kind === 'months' ? d.months : 'non specificata'
}
