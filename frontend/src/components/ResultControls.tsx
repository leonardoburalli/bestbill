import { useId, useState } from 'react'
import { parseItalianNumber } from '../lib/consumption'
import type { CompareFilters, PriceType, Scenario, SourceFilter } from '../types'
import { btnSecondary, FieldError, inputBase, inputBorder, Segmented, Spinner } from './ui'

const DURATION_OPTIONS = [
  { value: '', label: 'Qualsiasi' },
  { value: '12', label: 'Almeno 12 mesi' },
  { value: '24', label: 'Almeno 24 mesi' },
  { value: '36', label: 'Almeno 36 mesi' },
]

type Mode = Scenario['kind']

const fmtInput = (n: number) => String(n).replace('.', ',')

export default function ResultControls({
  scenario,
  filters,
  busy,
  scenarioError,
  onScenario,
  onFilters,
}: {
  scenario: Scenario
  filters: CompareFilters
  busy: boolean
  scenarioError?: string
  onScenario: (s: Scenario) => void
  onFilters: (f: CompareFilters) => void
}) {
  const [mode, setMode] = useState<Mode>(scenario.kind)
  const [pct, setPct] = useState(() =>
    scenario.kind === 'scaled' ? fmtInput(Math.round((scenario.factor - 1) * 100)) : '10',
  )
  const [flat, setFlat] = useState(() => (scenario.kind === 'flat' ? fmtInput(scenario.value) : '0,12'))
  const [touched, setTouched] = useState(false)
  const pctId = useId()
  const flatId = useId()
  const helpId = useId()
  const durationId = useId()
  const durationHelpId = useId()

  const pctNum = parseItalianNumber(pct)
  const flatNum = parseItalianNumber(flat)
  const pctErr = pctNum === null ? 'Scrivi un numero, per esempio 20 oppure -15.' : pctNum <= -100 ? 'La variazione deve essere superiore a -100%.' : undefined
  const flatErr = flatNum === null ? 'Scrivi un prezzo in €/kWh, per esempio 0,12.' : flatNum < 0 ? 'Il prezzo non può essere negativo.' : undefined

  const apply = () => {
    setTouched(true)
    if (mode === 'scaled' && !pctErr && pctNum !== null) onScenario({ kind: 'scaled', factor: 1 + pctNum / 100 })
    if (mode === 'flat' && !flatErr && flatNum !== null) onScenario({ kind: 'flat', value: flatNum })
  }

  const priceType = (filters.price_type ?? 'all') as PriceType | 'all'
  const source = (filters.source ?? 'all') as SourceFilter | 'all'

  return (
    <section aria-labelledby="h-controls" className="rounded-2xl border border-line bg-card p-5 sm:p-6">
      <div className="flex items-center justify-between gap-3">
        <h2 id="h-controls" className="font-display text-xl font-semibold">
          Filtra e prova scenari
        </h2>
        {busy && (
          <span className="flex items-center gap-2 text-sm text-ink-soft" aria-hidden="true">
            <Spinner size={16} /> Aggiorno…
          </span>
        )}
      </div>

      <div className="mt-4 grid gap-6 lg:grid-cols-2">
        <div className="space-y-4">
          <Segmented<PriceType | 'all'>
            legend="Tipo di prezzo"
            name="f-price"
            value={priceType}
            options={[
              { value: 'all', label: 'Tutti' },
              { value: 'fixed', label: 'Fisso' },
              { value: 'variable', label: 'Variabile' },
            ]}
            onChange={(v) => onFilters({ ...filters, price_type: v === 'all' ? null : v })}
          />
          <Segmented<SourceFilter | 'all'>
            legend="Tipo di offerta"
            name="f-source"
            value={source}
            options={[
              { value: 'all', label: 'Tutte' },
              { value: 'placet', label: 'PLACET' },
              { value: 'mlibero', label: 'Mercato libero' },
            ]}
            onChange={(v) => onFilters({ ...filters, source: v === 'all' ? null : v })}
          />
          <p className="max-w-sm text-sm leading-relaxed text-ink-soft">
            PLACET sono le offerte a condizioni standard stabilite da ARERA; le altre sono a libera scelta del
            fornitore.
          </p>
          <div>
            <label htmlFor={durationId} className="mb-2 block text-sm font-semibold text-ink">
              Durata minima
            </label>
            <select
              id={durationId}
              value={filters.min_duration_months ? String(filters.min_duration_months) : ''}
              onChange={(e) =>
                onFilters({ ...filters, min_duration_months: e.target.value ? Number(e.target.value) : null })
              }
              aria-describedby={durationHelpId}
              className={`${inputBase} ${inputBorder(false)} w-auto min-w-[13rem] pr-8`}
            >
              {DURATION_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            <p id={durationHelpId} className="mt-1.5 max-w-sm text-sm leading-relaxed text-ink-soft">
              Se scegli una durata minima, le offerte a durata indeterminata o non indicata non vengono mostrate.
            </p>
          </div>
        </div>

        <div>
          <Segmented<Mode>
            legend="Se il PUN nei prossimi 12 mesi…"
            name="f-scenario"
            value={mode}
            options={[
              { value: 'historical', label: 'Ripete il periodo' },
              { value: 'scaled', label: 'Più alto o più basso' },
              { value: 'flat', label: 'Valore fisso' },
            ]}
            onChange={(m) => {
              setMode(m)
              setTouched(false)
              if (m === 'historical') onScenario({ kind: 'historical' })
            }}
          />
          <p id={helpId} className="mt-2 max-w-md text-sm leading-relaxed text-ink-soft">
            Il PUN è il prezzo all'ingrosso dell'energia. «Ripete il periodo» vuol dire che, mese per mese,
            segue lo stesso andamento del periodo indicato. Cambia solo il costo delle offerte a prezzo
            variabile: quelle a prezzo fisso restano uguali.
          </p>

          {mode === 'scaled' && (
            <div className="mt-3">
              <label htmlFor={pctId} className="block text-sm font-semibold">
                Se il PUN nei prossimi 12 mesi cambiasse, di quanto rispetto al periodo indicato?
              </label>
              <div className="mt-1.5 flex flex-wrap items-start gap-2">
                <div className="relative w-36">
                  <input
                    id={pctId}
                    type="text"
                    inputMode="decimal"
                    value={pct}
                    onChange={(e) => setPct(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && apply()}
                    aria-invalid={touched && pctErr ? true : undefined}
                    aria-describedby={helpId}
                    className={`${inputBase} ${inputBorder(touched && !!pctErr)} tabular pr-8 text-right`}
                  />
                  <span aria-hidden="true" className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm text-ink-soft">%</span>
                </div>
                <button type="button" onClick={apply} disabled={busy} className={btnSecondary}>Applica</button>
              </div>
              <p className="mt-1 text-xs text-ink-soft">Per esempio 20 = PUN più alto del 20%; -15 = più basso del 15%.</p>
              {touched && pctErr && <FieldError>{pctErr}</FieldError>}
            </div>
          )}

          {mode === 'flat' && (
            <div className="mt-3">
              <label htmlFor={flatId} className="block text-sm font-semibold">
                Se il PUN nei prossimi 12 mesi fosse in media pari a
              </label>
              <div className="mt-1.5 flex flex-wrap items-start gap-2">
                <div className="relative w-44">
                  <input
                    id={flatId}
                    type="text"
                    inputMode="decimal"
                    value={flat}
                    onChange={(e) => setFlat(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && apply()}
                    aria-invalid={touched && flatErr ? true : undefined}
                    aria-describedby={helpId}
                    className={`${inputBase} ${inputBorder(touched && !!flatErr)} tabular pr-16 text-right`}
                  />
                  <span aria-hidden="true" className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm text-ink-soft">€/kWh</span>
                </div>
                <button type="button" onClick={apply} disabled={busy} className={btnSecondary}>Applica</button>
              </div>
              {touched && flatErr && <FieldError>{flatErr}</FieldError>}
            </div>
          )}
          {scenarioError && <FieldError>{scenarioError}</FieldError>}
        </div>
      </div>
    </section>
  )
}
