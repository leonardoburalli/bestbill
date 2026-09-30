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

/** Start (YYYY-MM) of the 12 months ending with the last complete month. */
export function defaultStartMonth(today: Date = new Date()): string {
  // last complete month = previous month; start = 11 months before that
  return ym(today.getFullYear(), today.getMonth() - 12)
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

/** Selectable start months, newest first. The newest one is defaultStartMonth. */
export function monthOptions(today: Date = new Date(), yearsBack = 3): string[] {
  const newest = parts(defaultStartMonth(today))
  return Array.from({ length: yearsBack * 12 }, (_, i) => ym(newest[0], newest[1] - i))
}
