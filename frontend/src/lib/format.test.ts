import { energyPriceText, energyPriceView, formatDate, formatDuration, formatDurationShort, formatEnergyPrice, formatEur, formatEurCompact, formatEurPerKwh, formatKwh } from './format'

const norm = (s: string) => s.replace(/[\u00a0\u202f]/g, ' ')

describe('format', () => {
  it('formatEur', () => expect(norm(formatEur(1234.5))).toBe('1.234,50 €'))
  it('formatEurCompact', () => expect(norm(formatEurCompact(1234.5))).toBe('1.235 €'))
  it('formatEurPerKwh', () => expect(formatEurPerKwh(0.137)).toBe('0,1370 €/kWh'))
  it('formatEnergyPrice', () => {
    expect(formatEnergyPrice(0.1604, 'fixed')).toBe('0,1604 €/kWh')
    expect(formatEnergyPrice(0.012, 'pun_spread')).toBe('PUN + 0,0120 €/kWh')
  })
  it('formatEnergyPrice shows a negative spread with a minus', () => {
    expect(formatEnergyPrice(-0.001, 'pun_spread')).toBe('PUN − 0,0010 €/kWh')
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
    expect(formatDuration({ price_type: 'fixed', duration_months: null, duration_open_ended: true })).toBe('Durata non specificata')
    expect(formatDuration({ ...base, price_type: 'fixed' })).toBe('Durata non specificata')
  })
  it('treats missing fields as unknown, never NaN/undefined', () => {
    expect(formatDuration({ price_type: 'fixed' })).toBe('Durata non specificata')
    expect(formatDuration({ price_type: 'fixed', duration_months: Number.NaN })).toBe('Durata non specificata')
    expect(formatDurationShort({})).toBe('—')
  })
  it('formatDurationShort', () => {
    expect(formatDurationShort({ duration_months: 24 })).toBe('24 mesi')
    expect(formatDurationShort({ duration_open_ended: true })).toBe('Non specificata')
  })
})

describe('energyPriceView', () => {
  it('shows the after-discount price with the list price and discount underneath', () => {
    const v = energyPriceView({
      energy_price_eur_kwh: 0.2079, energy_price_kind: 'fixed',
      energy_price_after_discounts_eur_kwh: 0.1455, energy_discount_pct: 30,
    })
    expect(v.main).toBe('0,1455 €/kWh')
    expect(v.note).toBe('listino 0,2079 · sconto 30% incluso')
  })
  it('works for a spread over PUN', () => {
    const v = energyPriceView({
      energy_price_eur_kwh: 0.022, energy_price_kind: 'pun_spread',
      energy_price_after_discounts_eur_kwh: 0.0154, energy_discount_pct: 30,
    })
    expect(v.main).toBe('PUN + 0,0154 €/kWh')
    expect(v.note).toBe('listino PUN + 0,0220 · sconto 30% incluso')
    expect(energyPriceText({ energy_price_eur_kwh: 0.022, energy_price_kind: 'pun_spread', energy_price_after_discounts_eur_kwh: 0.0154, energy_discount_pct: 30 })).toBe(
      'PUN + 0,0154 €/kWh (listino PUN + 0,0220 · sconto 30% incluso)',
    )
  })
  it('works out the percentage when the API does not send it, with a decimal comma', () => {
    const v = energyPriceView({ energy_price_eur_kwh: 0.2, energy_price_kind: 'fixed', energy_price_after_discounts_eur_kwh: 0.1795 })
    expect(v.note).toBe('listino 0,2000 · sconto 10,3% incluso')
  })
  it('no note when there is no discount, or when the new field is missing', () => {
    expect(energyPriceView({ energy_price_eur_kwh: 0.1604, energy_price_kind: 'fixed', energy_price_after_discounts_eur_kwh: 0.1604, energy_discount_pct: null }))
      .toEqual({ main: '0,1604 €/kWh', note: null })
    expect(energyPriceView({ energy_price_eur_kwh: 0.1604, energy_price_kind: 'fixed' })).toEqual({ main: '0,1604 €/kWh', note: null })
  })
  it('never shows NaN / undefined', () => {
    expect(energyPriceView({}).main).toBe('—')
  })
})
