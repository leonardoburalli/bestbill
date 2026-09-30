import type { ResultItem } from '../types'

/**
 * Break-even is against the cheapest eligible FIXED offer (core/models.py
 * BreakEvenStatus). Only variable offers have it.
 */
export function describeBreakEven(item: ResultItem): string | null {
  switch (item.break_even_status) {
    case 'cheaper_below': {
      if (item.break_even_pun_eur_kwh === null) return null
      const v = item.break_even_pun_eur_kwh.toLocaleString('it-IT', {
        minimumFractionDigits: 4,
        maximumFractionDigits: 4,
      })
      return `Conviene rispetto alla migliore fissa se il PUN medio resta sotto ${v} €/kWh`
    }
    case 'never_cheaper':
      return 'Non conviene rispetto alla migliore fissa a nessun livello di PUN'
    case 'always_cheaper':
      return 'Conviene rispetto alla migliore fissa a qualsiasi livello di PUN'
    default:
      return null
  }
}
