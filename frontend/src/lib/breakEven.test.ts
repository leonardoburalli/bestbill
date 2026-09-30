import type { ResultItem } from '../types'
import { describeBreakEven } from './breakEven'

const item = (p: Partial<ResultItem>) => p as ResultItem

describe('describeBreakEven', () => {
  it('cheaper_below', () =>
    expect(describeBreakEven(item({ break_even_status: 'cheaper_below', break_even_pun_eur_kwh: 0.1234 }))).toBe(
      'Conviene rispetto alla migliore fissa se il PUN medio resta sotto 0,1234 €/kWh'))
  it('never_cheaper', () =>
    expect(describeBreakEven(item({ break_even_status: 'never_cheaper', break_even_pun_eur_kwh: -0.01 }))).toBe(
      'Non conviene rispetto alla migliore fissa a nessun livello di PUN'))
  it('always_cheaper', () =>
    expect(describeBreakEven(item({ break_even_status: 'always_cheaper' }))).toBe(
      'Conviene rispetto alla migliore fissa a qualsiasi livello di PUN'))
  it('null', () => expect(describeBreakEven(item({ break_even_status: null }))).toBeNull())
  it('cheaper_below without value', () =>
    expect(describeBreakEven(item({ break_even_status: 'cheaper_below', break_even_pun_eur_kwh: null }))).toBeNull())
})
