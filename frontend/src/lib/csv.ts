import type { Assumptions, ResultItem } from '../types'

const SEP = ';'

type Cell = string | number | { num: string } | null | undefined

/** Number with fixed decimals, Italian decimal comma, never formula-guarded. */
const num = (n: number, d: number): Cell => ({ num: n.toFixed(d).replace('.', ',') })

function cell(v: Cell): string {
  if (v === null || v === undefined) return ''
  if (typeof v === 'object') return v.num
  let s = typeof v === 'number' ? String(v).replace('.', ',') : v
  // neutralise spreadsheet formula injection in text
  if (typeof v === 'string' && /^[=+\-@\t\r]/.test(s)) s = `'${s}`
  return /[";\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

const row = (cells: Cell[]) => cells.map(cell).join(SEP)

const HEADER = [
  'Posizione', 'Fornitore', 'Offerta', 'Tipo prezzo', 'Fonte',
  'Costo (EUR)', 'CCV (€/anno)', 'Differenza dalla migliore (EUR)', 'Costo effettivo (EUR/kWh)',
  'PUN di pareggio (EUR/kWh)', 'Una tantum (EUR)', 'Valida fino al', 'Link',
]

export function buildResultsCsv(results: ResultItem[], assumptions: Assumptions): string {
  const lines: string[] = [row(HEADER)]
  for (const r of results) {
    lines.push(
      row([
        r.rank, r.supplier, r.name, r.price_type === 'fixed' ? 'Fisso' : 'Variabile', r.source,
        num(r.cost_eur, 2), num(r.breakdown.fixed_fees, 2), num(r.delta_vs_best_eur, 2), num(r.eur_per_kwh_effective, 4),
        r.break_even_pun_eur_kwh === null ? null : num(r.break_even_pun_eur_kwh, 4),
        num(r.one_off_fee_eur, 2), r.valid_to, r.url,
      ]),
    )
  }
  lines.push('')
  lines.push(row(['Nota', `Importi: ${assumptions.cost_label}`]))
  lines.push(row(['Periodo', `${assumptions.period_start} - ${assumptions.period_end}`]))
  lines.push(row(['Ipotesi', assumptions.statement]))
  return '\uFEFF' + lines.join('\r\n') + '\r\n'
}

export function downloadText(filename: string, content: string, mime: string): void {
  const blob = new Blob([content], { type: `${mime};charset=utf-8` })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 0)
}
