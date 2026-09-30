import type { RefObject } from 'react'
import type { useApiStatus, useComuniSearch } from '../hooks'
import { formatDate } from '../lib/format'
import { buildMonths, formatMonthLong } from '../lib/months'
import DataShortcuts from './DataShortcuts'
import HouseholdFields from './HouseholdFields'
import ImportReport from './ImportReport'
import MonthGrid from './MonthGrid'
import StatusBanner from './StatusBanner'
import { ArrowRightIcon } from './icons'
import { btnPrimary, Notice, SectionCard } from './ui'
import type { ConsumptionForm } from './formState'

type ApiStatusValue = ReturnType<typeof useApiStatus>

export default function ConsumptionStep({
  cf,
  search,
  api,
  onSubmit,
  summaryRef,
}: {
  cf: ConsumptionForm
  search: ReturnType<typeof useComuniSearch>
  api: ApiStatusValue
  onSubmit: () => void
  summaryRef: RefObject<HTMLDivElement | null>
}) {
  const { check, mapped, attempted, note, report } = cf
  const ready = api.status === 'ready'
  const months = buildMonths(cf.form.start)
  // Mesi dei 12 scelti che non sono nel file, e tra questi quelli ancora da compilare a mano.
  const imported = cf.form.imported ? new Set(cf.form.imported.map((m) => m.month)) : null
  const absent = imported ? months.filter((m) => !imported.has(m)) : []
  const pending = absent.filter((m) => !cf.form.cells[months.indexOf(m)].kwh.trim())

  // Elenco dei problemi da mostrare in cima dopo un tentativo di invio
  const problems: { href: string; text: string }[] = []
  if (attempted) {
    check.rows.forEach((r, i) => {
      const m = mapped.rows[i]
      const label = formatMonthLong(months[i])
      if (m?.kwh ?? r.kwh) problems.push({ href: `#kwh-${i}`, text: `${label}: ${m?.kwh ?? r.kwh}` })
      const b = m?.bands ?? m?.general ?? (cf.form.useBands ? r.bands : undefined)
      if (b) problems.push({ href: `#f1-${i}`, text: `${label}: ${b}` })
    })
    if (check.power || mapped.power) problems.push({ href: '#', text: `Potenza: ${mapped.power ?? check.power}` })
    if (mapped.comune) problems.push({ href: '#', text: `Comune: ${mapped.comune}` })
    mapped.general.forEach((g) => problems.push({ href: '#', text: g }))
  }
  const uniqueProblems = problems.filter((p, i) => problems.findIndex((q) => q.text === p.text) === i)

  return (
    <div className="animate-rise space-y-6">
      <div className="max-w-2xl">
        <h1 id="step-heading" tabIndex={-1} className="focus:outline-none font-display text-4xl font-semibold leading-[1.1] tracking-tight sm:text-5xl">
          Quanto spenderesti nei prossimi 12 mesi con ciascuna offerta luce?
        </h1>
        <p className="mt-4 text-lg leading-relaxed text-ink-soft">
          Indica quanta luce hai consumato in un anno. Calcoliamo quanto spenderesti nei prossimi 12 mesi con
          ciascuna offerta disponibile oggi, se consumassi allo stesso modo. Gratuito, senza registrazione.
        </p>
        {api.status === 'ready' && api.meta && (
          <p className="mt-3 text-sm text-ink-soft">
            Catalogo aggiornato al <strong className="text-ink">{formatDate(api.meta.snapshot_date)}</strong>:{' '}
            {api.meta.counts.included.toLocaleString('it-IT')} offerte confrontate.
          </p>
        )}
      </div>

      <StatusBanner api={api} />

      <form
        noValidate
        onSubmit={(e) => {
          e.preventDefault()
          onSubmit()
        }}
        className="space-y-6"
      >
        <SectionCard
          headingId="h-consumi"
          title="I tuoi consumi di riferimento"
          description="Ti servono i kWh consumati mese per mese in 12 mesi già passati. Li importi da Portale Consumi oppure li copi dalle bollette o dall'area clienti del tuo fornitore."
        >
          <DataShortcuts cf={cf} />
          {report && <ImportReport report={report} absent={absent} pending={pending} />}
          {note && (
            <Notice tone="ok" role="status" className="mt-4">
              {note}
            </Notice>
          )}
          <div className="my-6 perforation" aria-hidden="true" />
          <MonthGrid cf={cf} />
        </SectionCard>

        <SectionCard
          headingId="h-casa"
          title="La tua fornitura"
          description="Servono per escludere le offerte che non potresti sottoscrivere e per calcolare la quota potenza."
        >
          <HouseholdFields cf={cf} search={search} />
        </SectionCard>

        {uniqueProblems.length > 0 && (
          <div
            ref={summaryRef}
            tabIndex={-1}
            role="alert"
            className="rounded-xl border-2 border-brick bg-brick-soft px-5 py-4"
          >
            <p className="font-semibold text-brick">
              {uniqueProblems.length === 1 ? 'C\'è un dato da correggere' : `Ci sono ${uniqueProblems.length} dati da correggere`}
            </p>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-[0.95rem]">
              {uniqueProblems.slice(0, 6).map((p) => (
                <li key={p.text}>
                  {p.href !== '#' ? (
                    <a href={p.href} className="underline underline-offset-2" onClick={(e) => {
                      e.preventDefault()
                      document.querySelector<HTMLElement>(p.href)?.focus()
                    }}>
                      {p.text}
                    </a>
                  ) : (
                    p.text
                  )}
                </li>
              ))}
              {uniqueProblems.length > 6 && <li>…e altri {uniqueProblems.length - 6}.</li>}
            </ul>
          </div>
        )}

        <div className="flex flex-col items-start gap-3 rounded-2xl border border-forest-line bg-forest-soft p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6">
          <p className="max-w-md text-sm leading-relaxed text-ink-soft">
            Il confronto riguarda solo il costo della <strong className="text-ink">materia energia</strong>, IVA
            esclusa. Non comprende costi di rete, oneri di sistema e imposte. È una simulazione: ipotizza che nei
            prossimi 12 mesi tu consumi come nel periodo indicato e, per le offerte a prezzo variabile, che il
            PUN ripeta lo stesso andamento. Non è una previsione.
          </p>
          <div className="w-full sm:w-auto">
            <button type="submit" disabled={!ready} className={`${btnPrimary} w-full sm:w-auto`}>
              Confronta le offerte <ArrowRightIcon size={18} />
            </button>
            {!ready && (
              <p className="mt-1.5 text-center text-xs text-ink-soft sm:text-right">
                {api.status === 'unreachable' || api.status === 'no-catalog'
                  ? 'Servizio non disponibile al momento.'
                  : 'Attendo che il servizio sia pronto…'}
              </p>
            )}
          </div>
        </div>
      </form>
    </div>
  )
}
