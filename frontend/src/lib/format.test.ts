import { formatDate, formatEur, formatEurCompact, formatEurPerKwh, formatKwh } from './format'

const norm = (s: string) => s.replace(/[\u00a0\u202f]/g, ' ')

describe('format', () => {
  it('formatEur', () => expect(norm(formatEur(1234.5))).toBe('1.234,50 €'))
  it('formatEurCompact', () => expect(norm(formatEurCompact(1234.5))).toBe('1.235 €'))
  it('formatEurPerKwh', () => expect(formatEurPerKwh(0.137)).toBe('0,1370 €/kWh'))
  it('formatKwh groups 4-digit numbers', () => {
    expect(formatKwh(3200)).toBe('3.200 kWh')
    expect(formatKwh(180)).toBe('180 kWh')
  })
  it('formatDate is local, not UTC-shifted', () => {
    expect(formatDate('2026-09-29')).toBe('29 set 2026')
    expect(formatDate('2026-01-01')).toBe('1 gen 2026')
  })
})
