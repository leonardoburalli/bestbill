/**
 * Main application: state machine that drives the two-step flow.
 *
 * States:
 *   idle → computing → results → idle (back)
 *   any → error
 */
import { useState, useCallback, useEffect } from 'react'
import { apiClient } from './types'
import type {
  Health,
  CatalogMeta,
  SampleHousehold,
  MonthInput,
  CompareRequest,
  CompareResponse,
  Comune,
  Residency,
  Scenario,
  PriceType,
} from './types'
import ConsumptionInput from './components/ConsumptionInput'
import ResultsPage from './components/ResultsPage'
import LoadingState from './components/LoadingState'
import ErrorState from './components/ErrorState'
import Footer from './components/Footer'

type AppState = 'checking' | 'ready' | 'computing' | 'results' | 'error'

interface ConsumptionData {
  months: MonthInput[]
  bands: boolean // whether user entered F1/F2/F3
  istatComune: string | null
  residency: Residency
  committedPower: number
}

export default function App() {
  const [state, setState] = useState<AppState>('checking')
  const [health, setHealth] = useState<Health | null>(null)
  const [catalogMeta, setCatalogMeta] = useState<CatalogMeta | null>(null)
  const [sampleData, setSampleData] = useState<SampleHousehold | null>(null)
  const [comuni, setComuni] = useState<Comune[]>([])
  const [error, setError] = useState<string | null>(null)
  const [results, setResults] = useState<CompareResponse | null>(null)

  const [consumption, setConsumption] = useState<ConsumptionData>({
    months: [],
    bands: false,
    istatComune: null,
    residency: 'resident',
    committedPower: 3.0,
  })

  const [scenario, setScenario] = useState<Scenario>({ kind: 'historical' })
  const [priceFilter, setPriceFilter] = useState<PriceType | null>(null)
  const [sourceFilter, setSourceFilter] = useState<'placet' | 'mlibero' | null>(null)

  // Initial health check
  useEffect(() => {
    let cancelled = false
    apiClient
      .health()
      .then((h) => {
        if (!cancelled) {
          setHealth(h)
          setState(h.catalog_loaded ? 'ready' : 'error')
          if (!h.catalog_loaded) {
            setError('Il catalogo delle offerte non è ancora disponibile. Riprova tra poco.')
          }
        }
      })
      .catch(() => {
        if (!cancelled) {
          setState('error')
          setError('Impossibile connettersi al server. Controlla la tua connessione.')
        }
      })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Load catalog meta + sample when ready
  useEffect(() => {
    if (state !== 'ready') return
    let cancelled = false
    Promise.all([
      apiClient.catalogMeta().catch(() => null),
      apiClient.sample().catch(() => null),
    ]).then(([meta, sample]) => {
      if (!cancelled) {
        setCatalogMeta(meta)
        setSampleData(sample)
      }
    })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state])

  const handleSearchComuni = useCallback(async (q: string) => {
    if (q.length < 2) { setComuni([]); return }
    try {
      const found = await apiClient.comuni(q)
      setComuni(found)
    } catch {
      setComuni([])
    }
  }, [])

  const handleLoadSample = useCallback(() => {
    if (!sampleData) return
    const months = sampleData.months.map((m) => ({
      month: m.month,
      kwh: m.kwh,
    }))
    setConsumption((prev) => ({
      ...prev,
      months,
      bands: false,
    }))
  }, [sampleData])

  const handleConsumptionChange = useCallback((data: ConsumptionData) => {
    setConsumption(data)
  }, [])

  const handleCompare = useCallback(async () => {
    if (consumption.months.length !== 12) return
    setState('computing')
    setError(null)
    setResults(null)

    const body: CompareRequest = {
      consumption: consumption.months,
      residency: consumption.residency,
      istat_comune: consumption.istatComune,
      committed_power_kw: consumption.committedPower,
      scenario,
      filters: {
        price_type: priceFilter,
        source: sourceFilter,
      },
      top_n: 50,
    }

    try {
      const response = await apiClient.compare(body)
      setResults(response)
      setState('results')
    } catch (err) {
      setState('error')
      setError(err instanceof Error ? err.message : 'Errore durante il confronto.')
    }
  }, [consumption, scenario, priceFilter, sourceFilter])

  const handleBack = useCallback(() => {
    setState('ready')
    setResults(null)
  }, [])

  if (state === 'checking') {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <LoadingState message="Caricamento del catalogo offerte..." />
      </div>
    )
  }

  if (state === 'error') {
    return (
      <div className="min-h-screen">
        <ErrorState message={error} onRetry={handleBack} />
        <Footer meta={catalogMeta} />
      </div>
    )
  }

  return (
    <div className="min-h-screen">
      <header className="bg-white border-b border-surface/50">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center gap-3">
          <span className="text-2xl">⚡</span>
          <div>
            <h1 className="text-xl font-bold text-brand-dark">BestBill</h1>
            <p className="text-xs text-text-muted">
              {health?.catalog_loaded
                ? `Catalogo: ${health.snapshot_date ? new Date(health.snapshot_date).toLocaleDateString('it-IT') : 'data non disponibile'}`
                : ''}
            </p>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-6">
        {state === 'ready' && (
          <ConsumptionInput
            consumption={consumption}
            comuni={comuni}
            onSearchComuni={handleSearchComuni}
            onLoadSample={handleLoadSample}
            onConsumptionChange={handleConsumptionChange}
            onCompare={handleCompare}
          />
        )}

        {state === 'computing' && (
          <LoadingState message="Sto confrontando le offerte per il tuo profilo..." />
        )}

        {state === 'results' && results && (
          <ResultsPage
            response={results}
            scenario={scenario}
            setScenario={setScenario}
            priceFilter={priceFilter}
            setPriceFilter={setPriceFilter}
            sourceFilter={sourceFilter}
            setSourceFilter={setSourceFilter}
            onBack={handleBack}
          />
        )}
      </main>

      <Footer meta={catalogMeta} />
    </div>
  )
}
