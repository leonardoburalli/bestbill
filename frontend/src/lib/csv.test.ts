import type { Assumptions, ResultItem } from '../types'
import { buildResultsCsv } from './csv'

const r = (p: Partial<ResultItem>): ResultItem => ({
  rank: 1, supplier: 'Acme; "Energia"', name: 'Offerta, uno', price_type: 'fixed', source: 'placet',
  cost_eur: 1234.5, delta_vs_best_eur: 0, eur_per_kwh_effective: 0.137,
  energy_price_eur_kwh: 0.1, energy_price_kind: 'fixed', break_even_pun_eur_kwh: null,
  one_off_fee_eur: 0, breakdown: { fixed_fees: 120 } as ResultItem['breakdown'], valid_to: '2026-12-31', url: 'https://a.it', ...p,
} as ResultItem)

const assumptions = {
  cost_label: 'costo materia energia (IVA esclusa)', period_start: '2025-01-01', period_end: '2025-12-01',
  statement: 'Backtest, non previsione.',
} as Assumptions

describe('buildResultsCsv', () => {
  const csv = buildResultsCsv([r({}), r({ rank: 2, supplier: '=HYPERLINK("x")', delta_vs_best_eur: -3 })], assumptions)
  const lines = csv.split('\r\n')
  it('starts with BOM and header, uses semicolons', () => {
    expect(csv.charCodeAt(0)).toBe(0xfeff)
    expect(lines[0].slice(1).split(';')[0]).toBe('Posizione')
  })
  it('quotes fields containing ; and " (RFC 4180)', () => {
    expect(lines[1]).toContain('"Acme; ""Energia"""')
  })
  it('Italian decimal commas', () => {
    expect(lines[1]).toContain(';1234,50;')
    expect(lines[1]).toContain(';0,1370;')
    expect(lines[2]).toContain(';-3,00;')
  })
  it('has a CCV column right after the cost column', () => {
    const header = lines[0].slice(1).split(';')
    const i = header.indexOf('CCV (€/anno)')
    expect(i).toBe(header.indexOf('Costo (EUR)') + 1)
    expect(lines[1]).toContain(';1234,50;120,00;0,00;')
  })
  it('writes a zero CCV as 0,00, not blank', () => {
    const z = buildResultsCsv([r({ breakdown: { fixed_fees: 0 } as ResultItem['breakdown'] })], assumptions)
    expect(z.split('\r\n')[1]).toContain(';1234,50;0,00;0,00;')
  })
  it('has energy price and all-in average columns', () => {
    const header = lines[0].slice(1).split(';')
    expect(header).toContain('Prezzo energia (€/kWh)')
    expect(header).toContain('Costo medio tutto incluso (€/kWh)')
    expect(header).not.toContain('Costo effettivo (EUR/kWh)')
    expect(lines[1]).toContain(';0,00;0,1000;0,1370;')
  })
  it('prefixes PUN for spread offers', () => {
    const p = buildResultsCsv([r({ price_type: 'variable', energy_price_kind: 'pun_spread', energy_price_eur_kwh: 0.012 })], assumptions)
    expect(p.split('\r\n')[1]).toContain(';PUN + 0,0120;0,1370;')
  })
  it('neutralises formulas in text', () => expect(lines[2]).toContain("'=HYPERLINK"))
  it('includes label, period and statement', () => {
    expect(csv).toContain('costo materia energia (IVA esclusa)')
    expect(csv).toContain('Backtest, non previsione.')
    expect(csv.endsWith('\r\n')).toBe(true)
  })
})
