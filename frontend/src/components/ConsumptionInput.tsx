/**
 * Step 1: Consumption input form.
 *
 * Collects 12 months of kWh (optional F1/F2/F3), comune, residency, power.
 */
import { useState, useCallback } from 'react'
import type { MonthInput, Comune, Residency } from '../types'

interface Props {
  consumption: {
    months: MonthInput[]
    bands: boolean
    istatComune: string | null
    residency: Residency
    committedPower: number
  }
  comuni: Comune[]
  onSearchComuni: (q: string) => void
  onLoadSample: () => void
  onConsumptionChange: (data: {
    months: MonthInput[]
    bands: boolean
    istatComune: string | null
    residency: Residency
    committedPower: number
  }) => void
  onCompare: () => void
}

const MONTH_LABELS = [
  'Gen', 'Feb', 'Mar', 'Apr', 'Mag', 'Giu',
  'Lug', 'Ago', 'Set', 'Ott', 'Nov', 'Dic',
]

export default function ConsumptionInput({
  consumption,
  comuni,
  onSearchComuni,
  onLoadSample,
  onConsumptionChange,
  onCompare,
}: Props) {
  const [comuneQuery, setComuneQuery] = useState('')
  const [showComuni, setShowComuni] = useState(false)
  const [showBands, setShowBands] = useState(false)

  const handleMonthChange = useCallback(
    (index: number, kwh: string) => {
      const num = kwh === '' ? 0 : parseFloat(kwh)
      const months = consumption.months.map((m, i) =>
        i === index ? { ...m, kwh: isNaN(num) ? 0 : num } : m,
      )
      onConsumptionChange({ ...consumption, months })
    },
    [consumption, onConsumptionChange],
  )

  const handleBandChange = useCallback(
    (monthIndex: number, band: 'f1' | 'f2' | 'f3', value: string) => {
      const num = value === '' ? 0 : parseFloat(value)
      const months = consumption.months.map((m, i) => {
        if (i !== monthIndex) return m
        const key = band === 'f1' ? 'f1' : band === 'f2' ? 'f2' : 'f3'
        return {
          ...m,
          [key]: isNaN(num) ? 0 : num,
        }
      })
      onConsumptionChange({ ...consumption, months, bands: true })
    },
    [consumption, onConsumptionChange],
  )

  const handleResidencyChange = useCallback(
    (r: Residency) => {
      onConsumptionChange({ ...consumption, residency: r })
    },
    [consumption, onConsumptionChange],
  )

  const handlePowerChange = useCallback(
    (p: number) => {
      onConsumptionChange({ ...consumption, committedPower: p })
    },
    [consumption, onConsumptionChange],
  )

  const handleComuneSelect = useCallback(
    (comune: Comune) => {
      onConsumptionChange({
        ...consumption,
        istatComune: comune.codice,
      })
      setComuneQuery(comune.nome)
      setShowComuni(false)
    },
    [consumption, onConsumptionChange],
  )

  const handleComuneInput = useCallback(
    (q: string) => {
      setComuneQuery(q)
      setShowComuni(true)
      onSearchComuni(q)
    },
    [onSearchComuni],
  )

  const isComplete = consumption.months.length === 12 &&
    consumption.months.every((m) => m.kwh > 0)

  const totalKwh = consumption.months.reduce((sum, m) => sum + m.kwh, 0)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold mb-2">I tuoi consumi</h2>
        <p className="text-text-muted text-sm">
          Inserisci 12 mesi consecutivi di consumi (kWh). I dati non vengono salvati.
        </p>
      </div>

      {/* Sample button */}
      <button
        onClick={onLoadSample}
        className="w-full py-3 px-4 bg-brand-light text-brand-dark rounded-lg border border-brand/30 hover:bg-brand/20 transition-colors text-sm font-medium"
      >
        📋 Prova con una famiglia di esempio (dati sintetici)
      </button>

      {/* Comuni search */}
      <div className="space-y-1">
        <label className="block text-sm font-medium text-text">
          Comune (opzionale, per offerte vincolate)
        </label>
        <div className="relative">
          <input
            type="text"
            value={comuneQuery}
            onChange={(e) => handleComuneInput(e.target.value)}
            onFocus={() => setShowComuni(true)}
            onBlur={() => setTimeout(() => setShowComuni(false), 200)}
            placeholder="Cerca comune (es. Firenze)..."
            className="w-full px-3 py-2 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand/50"
          />
          {showComuni && comuni.length > 0 && (
            <ul className="absolute z-10 w-full mt-1 bg-white border border-border rounded-lg shadow-lg max-h-48 overflow-y-auto">
              {comuni.map((c) => (
                <li
                  key={c.codice}
                  onClick={() => handleComuneSelect(c)}
                  className="px-3 py-2 text-sm hover:bg-surface cursor-pointer border-b border-border/50 last:border-b-0"
                >
                  <span className="font-medium">{c.nome}</span>
                  <span className="text-text-muted ml-2">
                    ({c.sigla_provincia} – {c.regione})
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Residency */}
      <div className="space-y-1">
        <label className="block text-sm font-medium text-text">
          Tipo di cliente
        </label>
        <div className="flex gap-4">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              name="residency"
              checked={consumption.residency === 'resident'}
              onChange={() => handleResidencyChange('resident')}
              className="text-brand focus:ring-brand"
            />
            Residente
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              name="residency"
              checked={consumption.residency === 'non_resident'}
              onChange={() => handleResidencyChange('non_resident')}
              className="text-brand focus:ring-brand"
            />
            Non residente
          </label>
        </div>
      </div>

      {/* Power */}
      <div className="space-y-1">
        <label className="block text-sm font-medium text-text">
          Potenza impegnata: {consumption.committedPower.toFixed(1)} kW
        </label>
        <input
          type="range"
          min={0.5}
          max={20}
          step={0.5}
          value={consumption.committedPower}
          onChange={(e) => handlePowerChange(parseFloat(e.target.value))}
          className="w-full accent-brand"
        />
        <div className="flex justify-between text-xs text-text-muted">
          <span>0,5 kW</span>
          <span>20 kW</span>
        </div>
      </div>

      {/* Toggle bands */}
      <button
        onClick={() => setShowBands(!showBands)}
        className="text-sm text-brand hover:text-brand-dark transition-colors"
      >
        {showBands ? '▼' : '▶'} Inserisci fasce F1/F2/F3 (opzionale, dalla bolletta)
      </button>

      {/* 12-month grid */}
      <div className="bg-white rounded-xl border border-border p-4 space-y-4">
        <div className="grid grid-cols-12 gap-2 text-xs font-medium text-text-muted text-center">
          {MONTH_LABELS.map((label) => (
            <div key={label}>{label}</div>
          ))}
        </div>

        {/* kWh row */}
        <div className="grid grid-cols-12 gap-2">
          {consumption.months.map((m, i) => (
            <input
              key={`kwh-${i}`}
              type="number"
              inputMode="decimal"
              placeholder="—"
              value={m.kwh > 0 ? m.kwh : ''}
              onChange={(e) => handleMonthChange(i, e.target.value)}
              className="w-full px-2 py-2 text-center border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand/50"
            />
          ))}
        </div>

        {/* Total */}
        <div className="text-center text-sm font-medium">
          Totale annuo: <span className="text-brand-dark">{totalKwh.toFixed(0)} kWh</span>
        </div>

        {/* Band rows (optional) */}
        {showBands && (
          <div className="space-y-3 pt-3 border-t border-border">
            <p className="text-xs text-text-muted">
              Se conosci i consumi per fascia dalla bolletta, inseriscili qui.
              Altrimenti, la ripartizione standard verrà applicata automaticamente.
            </p>
            {(['f1', 'f2', 'f3'] as const).map((band) => (
              <div key={band} className="grid grid-cols-12 gap-2">
                {consumption.months.map((m, i) => (
                  <input
                    key={`${band}-${i}`}
                    type="number"
                    inputMode="decimal"
                    placeholder="—"
                    value={m[band] ? m[band]! : ''}
                    onChange={(e) => handleBandChange(i, band, e.target.value)}
                    className="w-full px-2 py-2 text-center border border-border rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-brand/50"
                  />
                ))}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Submit */}
      <button
        onClick={onCompare}
        disabled={!isComplete}
        className={`w-full py-3 px-4 rounded-lg text-sm font-semibold transition-all ${
          isComplete
            ? 'bg-brand text-white hover:bg-brand-dark'
            : 'bg-border text-text-muted cursor-not-allowed'
        }`}
      >
        {isComplete ? 'Confronta le offerte' : 'Inserisci tutti i 12 mesi con consumi > 0'}
      </button>
    </div>
  )
}
