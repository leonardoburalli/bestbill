/**
 * Assumptions banner: always visible above results.
 */
import type { Assumptions } from '../types'

interface Props {
  assumptions: Assumptions
}

export default function AssumptionsBanner({ assumptions }: Props) {
  return (
    <div className="bg-warm-light border border-warm/30 rounded-xl p-4">
      <p className="text-sm text-text">{assumptions.statement}</p>
      <div className="mt-3 text-xs text-text-muted space-y-1">
        <p>
          <strong>Periodo:</strong> {assumptions.period_start} → {assumptions.period_end}
        </p>
        <p>
          <strong>Split fasce:</strong> {assumptions.band_split_source === 'user' ? 'Inserito da te' : 'Standard (famiglia tipica)'}
        </p>
        {assumptions.istat_comune && (
          <p><strong>Comune ISTAT:</strong> {assumptions.istat_comune}</p>
        )}
        <p><strong>Potenza:</strong> {assumptions.committed_power_kw.toFixed(1)} kW</p>
        <p><strong>Residenza:</strong> {assumptions.residency === 'resident' ? 'Residente' : 'Non residente'}</p>
      </div>
    </div>
  )
}
