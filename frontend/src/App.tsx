/**
 * BestBill: due passi. 1) consumi  2) offerte.
 * Lo stato del modulo vive qui, così "Modifica i consumi" non perde nulla.
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { useApiStatus, useComparison, useComuniSearch, useDebouncedValue } from './hooks'
import { parseItalianNumber } from './lib/consumption'
import { buildMonths } from './lib/months'
import type { CompareFilters, Scenario } from './types'
import ConsumptionStep from './components/ConsumptionStep'
import Footer from './components/Footer'
import Header from './components/Header'
import type { Step } from './components/Header'
import ResultsStep from './components/ResultsStep'
import { buildRequest, comuneLabel, isInputField, useConsumptionForm } from './components/formState'

export default function App() {
  const api = useApiStatus()
  const search = useComuniSearch()
  const comparison = useComparison()
  // Ricerca per nome: un secondo confronto, solo per l'elenco. Miglior offerta e grafico restano su `comparison`.
  const searchCmp = useComparison()
  const [searchText, setSearchText] = useState('')
  const typed = searchText.trim()
  const debounced = useDebouncedValue(typed, 300)
  // Svuotare il campo vale subito, senza attendere i 300 ms.
  const searchTerm = typed === '' ? '' : debounced
  const cf = useConsumptionForm()

  const [step, setStep] = useState<Step>('input')
  const [scenario, setScenario] = useState<Scenario>({ kind: 'historical' })
  const [filters, setFilters] = useState<CompareFilters>({})
  // Dopo un nuovo invio non mostriamo i risultati del confronto precedente.
  const [fresh, setFresh] = useState(false)

  const summaryRef = useRef<HTMLDivElement>(null)
  const prevStep = useRef<Step>('input')

  const { form, check, setAttempted, setServerErrors } = cf
  const comune = search.selected

  const run = (s: Scenario, f: CompareFilters) => {
    comparison.run(buildRequest(form, comune, s, f))
    if (searchTerm) searchCmp.run(buildRequest(form, comune, s, f, searchTerm))
  }
  const loadMore = () =>
    (searchTerm ? searchCmp : comparison).loadMore(
      buildRequest(form, comune, scenario, filters, searchTerm || undefined),
    )

  const submit = () => {
    setAttempted(true)
    if (!check.ok) {
      requestAnimationFrame(() => summaryRef.current?.focus())
      return
    }
    setFresh(true)
    setStep('results')
    searchCmp.reset()
    run(scenario, filters)
  }

  const changeScenario = (s: Scenario) => {
    setScenario(s)
    run(s, filters)
  }
  const changeFilters = (f: CompareFilters) => {
    setFilters(f)
    run(scenario, f)
  }

  // Cambia la ricerca (dopo i 300 ms): si riparte dalla prima pagina, con filtri e scenario attuali.
  const prevTerm = useRef('')
  useEffect(() => {
    if (prevTerm.current === searchTerm) return
    prevTerm.current = searchTerm
    if (step !== 'results') return
    if (searchTerm) searchCmp.run(buildRequest(form, comune, scenario, filters, searchTerm))
    else searchCmp.reset()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchTerm])

  // Errori 422 sui dati dei consumi: si torna al passo 1 con gli errori sulle righe giuste.
  const handled = useRef<unknown>(null)
  useEffect(() => {
    const err = comparison.error
    if (comparison.status !== 'error' || !err || handled.current === err) return
    handled.current = err
    if (err.status === 422) {
      const mine = err.fieldErrors.filter((e) => isInputField(e.field))
      if (mine.length > 0) {
        setServerErrors(mine)
        setAttempted(true)
        setStep('input')
        requestAnimationFrame(() => summaryRef.current?.focus())
      }
    }
  }, [comparison.status, comparison.error, setServerErrors, setAttempted])

  useEffect(() => {
    if (comparison.status === 'success' || comparison.status === 'error') setFresh(false)
  }, [comparison.status])

  // Cambio di passo: torna in alto e porta il focus sul titolo.
  useEffect(() => {
    if (prevStep.current === step) return
    prevStep.current = step
    window.scrollTo({ top: 0 })
    document.getElementById('step-heading')?.focus({ preventScroll: true })
  }, [step])

  const months = useMemo(() => buildMonths(form.start), [form.start])
  const summary = {
    start: months[0],
    end: months[11],
    totalKwh: check.totalKwh,
    residency: form.residency,
    powerKw: parseItalianNumber(form.power) ?? 3,
    comune: comune ? comuneLabel(comune) : null,
  }

  const data = fresh && comparison.status === 'loading' ? null : comparison.data

  return (
    <div className="flex min-h-dvh flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-card focus:px-4 focus:py-2 focus:shadow-lg"
      >
        Vai al contenuto
      </a>
      <Header
        step={step}
        canOpenResults={comparison.data !== null && comparison.status !== 'idle'}
        onGoInput={() => setStep('input')}
        onGoResults={() => setStep('results')}
      />
      <main id="main" className={`mx-auto w-full flex-1 px-4 py-8 sm:px-6 sm:py-12 ${step === 'results' ? 'max-w-6xl' : 'max-w-5xl'}`}>
        {step === 'input' ? (
          <ConsumptionStep cf={cf} search={search} api={api} onSubmit={submit} summaryRef={summaryRef} />
        ) : (
          <ResultsStep
            comparison={comparison}
            data={data}
            summary={summary}
            scenario={scenario}
            filters={filters}
            onScenario={changeScenario}
            onFilters={changeFilters}
            searchCmp={searchCmp}
            searchText={searchText}
            searchTerm={searchTerm}
            onSearchText={setSearchText}
            onLoadMore={loadMore}
            onRetry={() => run(scenario, filters)}
            onBack={() => setStep('input')}
          />
        )}
      </main>
      <Footer meta={api.meta} />
    </div>
  )
}
