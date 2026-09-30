import { describeScenario } from '../lib/scenario'
import { formatDate } from '../lib/format'
import { formatMonthLong } from '../lib/months'
import type { Assumptions } from '../types'
import { InfoIcon } from './icons'

const ymOf = (s: string) => s.slice(0, 7)

/** Sempre visibile sopra i risultati: cosa stiamo davvero stimando. */
export default function AssumptionsStatement({
  a,
  snapshotDate,
}: {
  a: Assumptions
  snapshotDate: string
}) {
  const substituted = a.substituted_pun_months
  return (
    <section
      aria-labelledby="h-ipotesi"
      className="rounded-2xl border border-forest-line border-l-[6px] border-l-forest bg-card p-5 sm:p-6"
    >
      <div className="flex items-start gap-3">
        <span className="mt-1 text-forest"><InfoIcon size={22} /></span>
        <div className="min-w-0">
          <h2 id="h-ipotesi" className="font-display text-xl font-semibold">
            Cosa significa questa stima
          </h2>
          <p className="mt-2 leading-relaxed">{a.statement}</p>
          <p className="mt-2 leading-relaxed">
            <strong className="font-semibold">Importi: {a.cost_label}.</strong>{' '}
            <span className="text-ink-soft">
              Non comprendono IVA, costi di rete e gestione del contatore, oneri di sistema e imposte. È una
              stima retrospettiva, non una previsione di quanto pagherai.
            </span>
          </p>

          <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
            <div>
              <dt className="text-ink-soft">Periodo dei consumi e del PUN</dt>
              <dd className="font-medium">
                {formatMonthLong(ymOf(a.period_start))} – {formatMonthLong(ymOf(a.period_end))}
              </dd>
            </div>
            <div>
              <dt className="text-ink-soft">Scenario del PUN</dt>
              <dd className="font-medium">{describeScenario(a.scenario)}</dd>
            </div>
            <div>
              <dt className="text-ink-soft">Fasce F1/F2/F3</dt>
              <dd className="font-medium">
                {a.band_split_source === 'user' ? 'Indicate da te' : 'Ripartizione standard'}
              </dd>
            </div>
            <div>
              <dt className="text-ink-soft">Fornitura</dt>
              <dd className="font-medium">
                {a.residency === 'resident' ? 'Residente' : 'Non residente'}, {a.committed_power_kw.toLocaleString('it-IT')} kW
              </dd>
            </div>
            <div>
              <dt className="text-ink-soft">Offerte aggiornate al</dt>
              <dd className="font-medium">{formatDate(snapshotDate)}</dd>
            </div>
          </dl>

          {substituted.length > 0 && (
            <p className="mt-3 rounded-lg border border-amber-line bg-amber-soft px-3 py-2 text-sm leading-relaxed">
              Per {substituted.map((m) => formatMonthLong(ymOf(m))).join(', ')} il PUN definitivo non era ancora
              disponibile: abbiamo usato un valore sostitutivo.
            </p>
          )}

          <details className="group mt-4">
            <summary className="cursor-pointer select-none rounded-md py-1 text-[0.95rem] font-medium text-forest underline decoration-forest-line decoration-2 underline-offset-4">
              Come calcoliamo
            </summary>
            <div className="mt-2 space-y-2 text-sm leading-relaxed text-ink-soft">
              <p>
                Prendiamo i tuoi 12 mesi di consumi e calcoliamo quanto avrebbe speso ciascuna offerta attiva
                oggi, con le regole pubblicate da ARERA. Per le offerte a prezzo variabile usiamo il PUN
                (il prezzo all'ingrosso dell'energia) mese per mese, oppure lo scenario che scegli sotto.
              </p>
              <p>
                <strong className="text-ink">Incluso:</strong> prezzo dell'energia, quote fisse del fornitore,
                costi al kWh del fornitore, quota potenza, dispacciamento, costi una tantum e sconti sempre
                applicati.
              </p>
              <p>
                <strong className="text-ink">Non incluso:</strong> IVA, trasporto e gestione del contatore, oneri
                di sistema, accise e imposte, che sono uguali per tutte le offerte. Gli sconti che dipendono da
                condizioni (per esempio la domiciliazione) sono elencati a parte e non sono sottratti.
              </p>
              <p>
                Il risultato dice cosa sarebbe successo nel passato: non sappiamo come si muoveranno consumi e
                prezzi nei prossimi mesi.
              </p>
            </div>
          </details>
        </div>
      </div>
    </section>
  )
}
