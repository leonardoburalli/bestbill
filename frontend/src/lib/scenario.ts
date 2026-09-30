import type { Scenario } from '../types'

/** Mirrors core/models.py: Scaled.factor > 0, Flat.value >= 0 (€/kWh). */
export const SCENARIO_LIMITS = {
  factor: { min: 0, minExclusive: true, default: 1 },
  value: { min: 0, minExclusive: false, default: 0.12 },
} as const

const it = (n: number, d = 2) =>
  n.toLocaleString('it-IT', { minimumFractionDigits: 0, maximumFractionDigits: d })

export function describeScenario(s: Scenario): string {
  switch (s.kind) {
    case 'historical':
      return 'PUN storico mese per mese'
    case 'scaled': {
      const pct = Math.round((s.factor - 1) * 100)
      if (pct === 0) return 'PUN storico (×1)'
      return `PUN storico ${pct > 0 ? '+' : '−'}${it(Math.abs(pct), 0)}% (×${it(s.factor)})`
    }
    case 'flat':
      return `PUN costante a ${s.value.toLocaleString('it-IT', { minimumFractionDigits: 4, maximumFractionDigits: 4 })} €/kWh`
  }
}
