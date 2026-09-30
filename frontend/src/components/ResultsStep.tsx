import { lazy, Suspense } from 'react'
import type { ApiError } from '../api'
import type { useComparison } from '../hooks'
import { formatEur, formatKwh } from '../lib/format'
import { buildResultsCsv, downloadText } from '../lib/csv'
import { formatMonthShort } from '../lib/months'
import type { CompareFilters, CompareResponse, Scenario } from '../types'
import AssumptionsStatement from './AssumptionsStatement'
import BestOffer from './BestOffer'
import ExcludedOffers from './ExcludedOffers'
import { ArrowLeftIcon, DownloadIcon, RefreshIcon } from './icons'
import OfferList from './OfferList'
import ResultControls from './ResultControls'
import { errorMessage, ResultsError, ResultsSkeleton } from './ResultStates'
import { btnQuiet, btnSecondary, Notice, Spinner } from './ui'

const OfferChart = lazy(() => import('./OfferChart'))

type Comparison = ReturnType<typeof useComparison>

export interface ResultsSummary {
  start: string
  end: string
  totalKwh: number
  residency: 'resident' | 'non_resident'
  powerKw: number
  comune: string | null
}

export default function ResultsStep({
  comparison,
  data,
  summary,
  scenario,
  filters,
  onScenario,
  onFilters,
  onRetry,
  onBack,
}: {
  comparison: Comparison
  /** Dati da mostrare (già filtrati dal chiamante se appartengono a un invio precedente). */
  data: CompareResponse | null
  summary: ResultsSummary
  scenario: Scenario
  filters: CompareFilters
  onScenario: (s: Scenario) => void
  onFilters: (f: CompareFilters) => void
  onRetry: () => void
  onBack: () => void
}) {
  const { status, error, slow } = comparison
  const loading = status === 'loading'
  const filtersActive = !!(filters.price_type || filters.source)

  const exportCsv = () => {
    if (!data) return
    downloadText(
      `bestbill-offerte-${data.snapshot_date}.csv`,
      buildResultsCsv(data.results, data.assumptions),
      'text/csv',
    )
  }

  const live = loading
    ? 'Sto aggiornando i risultati.'
    : status === 'error'
      ? 'Non è stato possibile completare il confronto.'
      : data
        ? data.results.length > 0
          ? `Trovate ${data.total_matching} offerte. Per i prossimi 12 mesi la più economica è ${data.results[0].name} di ${data.results[0].supplier}, ${formatEur(data.results[0].cost_eur)}.`
          : 'Nessuna offerta trovata con questi criteri.'
        : ''

  return (
    <div className="animate-rise space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
        <div className="max-w-2xl">
          <h1 id="step-heading" tabIndex={-1} className="focus:outline-none font-display text-3xl font-semibold leading-tight tracking-tight sm:text-4xl">
            Quanto spenderesti nei prossimi 12 mesi
          </h1>
          <p className="mt-2 text-[0.95rem] leading-relaxed text-ink-soft">
            Se consumassi come tra {formatMonthShort(summary.start)} e {formatMonthShort(summary.end)} (
            {formatKwh(summary.totalKwh)} in 12 mesi), {summary.residency === 'resident' ? 'residente' : 'non residente'},{' '}
            {summary.powerKw.toLocaleString('it-IT')} kW
            {summary.comune ? `, ${summary.comune}` : ''}.
          </p>
        </div>
        <button type="button" onClick={onBack} className={btnSecondary}>
          <ArrowLeftIcon size={18} /> Modifica i consumi
        </button>
      </div>

      <p role="status" className="sr-only">{live}</p>

      {!data && loading && <ResultsSkeleton slow={slow} />}
      {!data && status === 'error' && error && <ResultsError error={error} onRetry={onRetry} onBack={onBack} />}

      {data && (
        <div aria-busy={loading} className="space-y-6">
          {loading && <UpdatingBar slow={slow} />}
          {status === 'error' && error && <InlineError error={error} onRetry={onRetry} />}

          <div className={`space-y-6 transition-opacity duration-200 ${loading ? 'opacity-55' : ''}`}>
            <AssumptionsStatement a={data.assumptions} snapshotDate={data.snapshot_date} />

            {data.results.length > 0 && (
              <BestOffer item={data.results[0]} next={data.results[0].rank === 1 ? data.results[1] : undefined} />
            )}
          </div>

          <ResultControls
            scenario={scenario}
            filters={filters}
            busy={loading}
            scenarioError={
              status === 'error' && error?.status === 422
                ? error.fieldErrors.filter((f) => f.field.startsWith('scenario')).map((f) => f.message).join(' ') || undefined
                : undefined
            }
            onScenario={onScenario}
            onFilters={onFilters}
          />

          <div className={`space-y-6 transition-opacity duration-200 ${loading ? 'opacity-55' : ''}`}>
            {data.results.length === 0 ? (
              <Notice
                tone="warn"
                title={
                  data.total_eligible === 0
                    ? 'Nessuna offerta adatta alla tua fornitura'
                    : 'Nessuna offerta con questi filtri'
                }
                action={
                  filtersActive ? (
                    <button type="button" onClick={() => onFilters({})} className={btnSecondary}>
                      Togli i filtri
                    </button>
                  ) : undefined
                }
              >
                {data.total_eligible === 0
                  ? 'Oggi nel catalogo non risultano offerte confrontabili per il tipo di utenza e il comune indicati. Prova a cambiare i dati inseriti.'
                  : `Ci sono ${data.total_eligible} offerte adatte a te, ma nessuna corrisponde ai filtri scelti.`}
              </Notice>
            ) : (
              <>
                <div className="flex flex-wrap items-end justify-between gap-3">
                  <div>
                    <h2 className="font-display text-2xl font-semibold">Tutte le offerte, dalla più economica</h2>
                    <p className="mt-1 text-sm text-ink-soft">
                      {data.results.length < data.total_matching
                        ? `Mostro le prime ${data.results.length} di ${data.total_matching}`
                        : `${data.total_matching} ${data.total_matching === 1 ? 'offerta' : 'offerte'}`}
                      {data.total_matching < data.total_eligible ? ` (su ${data.total_eligible} adatte a te)` : ''}. La
                      differenza è calcolata rispetto alla migliore in assoluto.
                    </p>
                  </div>
                  <button type="button" onClick={exportCsv} className={btnSecondary}>
                    <DownloadIcon size={18} /> Scarica CSV
                  </button>
                </div>

                <section aria-labelledby="h-chart" className="rounded-2xl border border-line bg-card p-4 sm:p-6">
                  <h3 id="h-chart" className="font-display text-lg font-semibold">
                    Le prime {Math.min(10, data.results.length)} a confronto
                  </h3>
                  <p className="mb-3 text-sm text-ink-soft">
                    Spesa stimata nei prossimi 12 mesi, se consumassi come nel periodo indicato. IVA esclusa. Le barre partono da zero.
                  </p>
                  <Suspense fallback={<div className="h-64 animate-pulse rounded-xl bg-paper-deep/60" role="status"><span className="sr-only">Carico il grafico…</span></div>}>
                    <OfferChart items={data.results} />
                  </Suspense>
                </section>

                <OfferList items={data.results} />
              </>
            )}

            <ExcludedOffers count={data.excluded_count} byReason={data.excluded_by_reason} />

            <p className="text-center text-sm text-ink-soft">
              <button type="button" onClick={onBack} className={btnQuiet}>
                <ArrowLeftIcon size={16} /> Torna a modificare i consumi
              </button>
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

function UpdatingBar({ slow }: { slow: boolean }) {
  return (
    <div role="status" className="flex items-center gap-3 rounded-xl border border-forest-line bg-forest-soft px-4 py-3 text-[0.95rem]">
      <Spinner />
      <span>
        <strong className="font-semibold">Aggiorno i risultati…</strong>{' '}
        <span className="text-ink-soft">
          {slow
            ? 'Il servizio sta rispondendo più lentamente del solito. Intanto vedi i risultati precedenti.'
            : 'Intanto vedi i risultati precedenti.'}
        </span>
      </span>
    </div>
  )
}

function InlineError({ error, onRetry }: { error: ApiError; onRetry: () => void }) {
  const { title, text } = errorMessage(error)
  return (
    <Notice
      tone="error"
      role="alert"
      title={`${title}. I risultati sotto sono quelli precedenti`}
      action={
        <button type="button" onClick={onRetry} className={btnSecondary}>
          <RefreshIcon size={18} /> Riprova
        </button>
      }
    >
      {text}
    </Notice>
  )
}
