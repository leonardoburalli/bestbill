import { lazy, Suspense } from 'react'
import type { ApiError } from '../api'
import type { useComparison } from '../hooks'
import { formatEur, formatKwh } from '../lib/format'
import { buildResultsCsv, downloadText } from '../lib/csv'
import { PAGE_SIZE } from './formState'
import { formatMonthShort } from '../lib/months'
import type { CompareFilters, CompareResponse, Scenario } from '../types'
import AssumptionsStatement from './AssumptionsStatement'
import BestOffer from './BestOffer'
import ExcludedOffers from './ExcludedOffers'
import { ArrowLeftIcon, DownloadIcon, RefreshIcon } from './icons'
import OfferList from './OfferList'
import ResultControls from './ResultControls'
import SearchBox from './SearchBox'
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
  searchCmp,
  searchText,
  searchTerm,
  onSearchText,
  onLoadMore,
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
  /** Second comparison, used only while a search is active (same filters, plus `search`). */
  searchCmp: Comparison
  /** What is typed in the box. */
  searchText: string
  /** The search currently applied (debounced); '' = no search. */
  searchTerm: string
  onSearchText: (v: string) => void
  /** Next page of whichever list is on screen (search hits while searching, otherwise all offers). */
  onLoadMore: () => void
  onRetry: () => void
  onBack: () => void
}) {
  const { status, error, slow } = comparison
  const loading = status === 'loading'
  const filtersActive = !!(filters.price_type || filters.source || filters.min_duration_months || filters.max_duration_months)

  // La lista mostra le offerte trovate dalla ricerca; miglior offerta e grafico restano sempre
  // quelli del confronto senza ricerca (`data`).
  const searching = searchTerm !== ''
  const listCmp = searching ? searchCmp : comparison
  const listData = searching ? searchCmp.data : data
  const listLoading = loading || (searching && searchCmp.status === 'loading')
  const listTotal = listData ? (searching ? (listData.search_matching ?? listData.results.length) : listData.total_matching) : 0
  const remaining = listData ? listTotal - listData.results.length : 0
  const sentence = (n: number) => `${n} ${n === 1 ? 'offerta' : 'offerte'}`

  const exportCsv = () => {
    if (!listData) return
    downloadText(
      `bestbill-offerte-${listData.snapshot_date}.csv`,
      buildResultsCsv(listData.results, listData.assumptions),
      'text/csv',
    )
  }

  const live = loading
    ? 'Sto aggiornando i risultati.'
    : status === 'error'
      ? 'Non è stato possibile completare il confronto.'
      : data
        ? searching && searchCmp.data
          ? searchCmp.data.results.length > 0
            ? `Trovate ${sentence(searchCmp.data.search_matching ?? searchCmp.data.results.length)} per «${searchTerm}».`
            : `Nessuna offerta di «${searchTerm}» con questi filtri.`
          : data.results.length > 0
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
              <BestOffer item={data.results[0]} next={data.results[1]} filtered={filtersActive} />
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
                      {sentence(data.total_matching)}
                      {data.total_matching < data.total_eligible ? ` (su ${data.total_eligible} adatte a te)` : ''}. La
                      differenza è calcolata rispetto alla più economica{filtersActive ? ' con questi filtri' : ''}.
                    </p>
                  </div>
                  <button type="button" onClick={exportCsv} disabled={!listData || listData.results.length === 0} className={btnSecondary}>
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

                <div className="space-y-4">
                  <SearchBox value={searchText} busy={searching && searchCmp.status === 'loading'} onChange={onSearchText} />

                  {searching && listData && listData.results.length > 0 && (
                    <p className="text-sm text-ink-soft">
                      {sentence(listTotal)} per «{searchTerm}» su {data.total_matching}.
                    </p>
                  )}
                </div>

                <div className={`space-y-4 transition-opacity duration-200 ${listLoading ? 'opacity-55' : ''}`} aria-busy={listLoading}>
                  {searching && searchCmp.status === 'error' && searchCmp.error && (
                    <InlineError error={searchCmp.error} onRetry={onRetry} />
                  )}

                  {searching && !listData && searchCmp.status !== 'error' && (
                    <div role="status" className="space-y-3">
                      <span className="sr-only">Cerco «{searchTerm}»…</span>
                      {[0, 1].map((i) => (
                        <div key={i} className="h-24 animate-pulse rounded-2xl bg-paper-deep/50" />
                      ))}
                    </div>
                  )}

                  {listData && listData.results.length === 0 && searchCmp.status !== 'error' && (
                    <Notice
                      tone="info"
                      title={`Nessuna offerta di «${searchTerm}» con questi filtri`}
                      action={
                        <>
                          <button type="button" onClick={() => onSearchText('')} className={btnSecondary}>
                            Cancella la ricerca
                          </button>
                          {filtersActive && (
                            <button type="button" onClick={() => onFilters({})} className={btnSecondary}>
                              Togli i filtri
                            </button>
                          )}
                        </>
                      }
                    >
                      Controlla come è scritto il nome oppure prova con una parte sola.
                      {filtersActive ? ' Se non basta, togli i filtri: l\'offerta potrebbe essere stata esclusa da quelli.' : ''}
                    </Notice>
                  )}

                  {listData && listData.results.length > 0 && (
                    <>
                      <OfferList items={listData.results} total={listData.total_matching} />

                      <div className="flex flex-col items-center gap-2 pt-1">
                        <p className="text-sm text-ink-soft" aria-live="polite">
                          Mostrate {listData.results.length} di {listTotal}
                        </p>
                        {listCmp.moreError && (
                          <p role="alert" className="text-sm text-brick">
                            {errorMessage(listCmp.moreError).title}. Riprova.
                          </p>
                        )}
                        {remaining > 0 && (
                          <button
                            type="button"
                            onClick={onLoadMore}
                            disabled={listLoading || listCmp.loadingMore}
                            className={btnSecondary}
                          >
                            {listCmp.loadingMore ? <Spinner size={16} /> : null}
                            {listCmp.loadingMore ? 'Carico…' : `Mostra altre ${Math.min(PAGE_SIZE, remaining)}`}
                          </button>
                        )}
                      </div>
                    </>
                  )}
                </div>
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
