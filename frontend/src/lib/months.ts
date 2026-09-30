const SHORT = ['gen', 'feb', 'mar', 'apr', 'mag', 'giu', 'lug', 'ago', 'set', 'ott', 'nov', 'dic']
const LONG = [
  'gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno',
  'luglio', 'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre',
]

function ym(year: number, month0: number): string {
  // normalise month overflow
  const total = year * 12 + month0
  const y = Math.floor(total / 12)
  const m = total - y * 12
  return `${String(y).padStart(4, '0')}-${String(m + 1).padStart(2, '0')}`
}

function parts(s: string): [number, number] {
  const [y, m] = s.split('-')
  return [Number(y), Number(m) - 1]
}

/** Previous calendar month (YYYY-MM): the latest month that is fully over. */
export function lastCompleteMonth(today: Date = new Date()): string {
  return ym(today.getFullYear(), today.getMonth() - 1)
}

/** end − 11 months */
export function startFromEnd(end: string): string {
  const [y, m] = parts(end)
  return ym(y, m - 11)
}

/** start + 11 months */
export function endFromStart(start: string): string {
  const [y, m] = parts(start)
  return ym(y, m + 11)
}

/** Start (YYYY-MM) of the 12 months ending with the last complete month. */
export function defaultStartMonth(today: Date = new Date()): string {
  return startFromEnd(lastCompleteMonth(today))
}

export function buildMonths(start: string): string[] {
  const [y, m] = parts(start)
  return Array.from({ length: 12 }, (_, i) => ym(y, m + i))
}

/** "2024-09" → "set 24" */
export function formatMonthShort(s: string): string {
  const [y, m] = parts(s)
  return `${SHORT[m]} ${String(y % 100).padStart(2, '0')}`
}

/** "2024-09" → "settembre 2024" */
export function formatMonthLong(s: string): string {
  const [y, m] = parts(s)
  return `${LONG[m]} ${y}`
}

/** Selectable end months, newest first. The newest one is lastCompleteMonth. */
export function endMonthOptions(today: Date = new Date(), yearsBack = 3): string[] {
  const [y, m] = parts(lastCompleteMonth(today))
  return Array.from({ length: yearsBack * 12 }, (_, i) => ym(y, m - i))
}

/** Selectable start months, newest first (each is end − 11 months). */
export function startMonthOptions(today: Date = new Date(), yearsBack = 3): string[] {
  return endMonthOptions(today, yearsBack).map(startFromEnd)
}

/** @deprecated alias of startMonthOptions */
export const monthOptions = startMonthOptions
