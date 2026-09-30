import { formatDate, formatDuration, formatDurationShort, formatEnergyPrice, formatEur, formatEurCompact, formatEurPerKwh, formatKwh } from './format'

const norm = (s: string) => s.replace(/[\u00a0\u202f]/g, ' ')

describe('format', () => {
  it('formatEur', () => expect(norm(formatEur(1234.5))).toBe('1.234,50 €'))
  it('formatEurCompact', () => expect(norm(formatEurCompact(1234.5))).toBe('1.235 €'))
  it('formatEurPerKwh', () => expect(formatEurPerKwh(0.137)).toBe('0,1370 €/kWh'))
  it('formatEnergyPrice', () => {
    expect(formatEnergyPrice(0.1604, 'fixed')).toBe('0,1604 €/kWh')
    expect(formatEnergyPrice(0.012, 'pun_spread')).toBe('PUN + 0,0120 €/kWh')
  })
  it('formatKwh groups 4-digit numbers', () => {
    expect(formatKwh(3200)).toBe('3.200 kWh')
    expect(formatKwh(180)).toBe('180 kWh')
  })
  it('formatDate is local, not UTC-shifted', () => {
    expect(formatDate('2026-09-29')).toBe('29 set 2026')
    expect(formatDate('2026-01-01')).toBe('1 gen 2026')
  })
})

describe('duration', () => {
  const base = { duration_months: null, duration_open_ended: false }
  it('formatDuration', () => {
    expect(formatDuration({ ...base, price_type: 'fixed', duration_months: 24 })).toBe('Prezzo bloccato 24 mesi')
    expect(formatDuration({ ...base, price_type: 'variable', duration_months: 24 })).toBe('Condizioni garantite 24 mesi')
    expect(formatDuration({ ...base, price_type: 'fixed', duration_months: 1 })).toBe('Prezzo bloccato 1 mese')
    expect(formatDuration({ price_type: 'fixed', duration_months: null, duration_open_ended: true })).toBe('Durata indeterminata')
    expect(formatDuration({ ...base, price_type: 'fixed' })).toBe('Durata non indicata')
  })
  it('treats missing fields as unknown, never NaN/undefined', () => {
    expect(formatDuration({ price_type: 'fixed' })).toBe('Durata non indicata')
    expect(formatDuration({ price_type: 'fixed', duration_months: Number.NaN })).toBe('Durata non indicata')
    expect(formatDurationShort({})).toBe('—')
  })
  it('formatDurationShort', () => {
    expect(formatDurationShort({ duration_months: 24 })).toBe('24 mesi')
    expect(formatDurationShort({ duration_open_ended: true })).toBe('Indeterminata')
  })
})
