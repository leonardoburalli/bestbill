const eur = new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', useGrouping: 'always', minimumFractionDigits: 2, maximumFractionDigits: 2 })
const eurCompact = new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', useGrouping: 'always', minimumFractionDigits: 0, maximumFractionDigits: 0 })
const perKwh = new Intl.NumberFormat('it-IT', { minimumFractionDigits: 4, maximumFractionDigits: 4 })
const kwh = new Intl.NumberFormat('it-IT', { maximumFractionDigits: 0, useGrouping: 'always' })

const MONTHS = ['gen', 'feb', 'mar', 'apr', 'mag', 'giu', 'lug', 'ago', 'set', 'ott', 'nov', 'dic']

export const formatEur = (n: number) => eur.format(n)
export const formatEurCompact = (n: number) => eurCompact.format(n)
export const formatEurPerKwh = (n: number) => `${perKwh.format(n)} €/kWh`
/** Advertised energy price: "0,1604 €/kWh" (fixed) or "PUN + 0,0120 €/kWh" (spread over PUN).
 *  "—" when the API did not send it (older API version). */
export const formatEnergyPrice = (n: number | null | undefined, kind: 'fixed' | 'pun_spread' | null | undefined) =>
  typeof n !== 'number' || !Number.isFinite(n)
    ? '—'
    : kind === 'pun_spread'
      ? `PUN + ${formatEurPerKwh(n)}`
      : formatEurPerKwh(n)
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
