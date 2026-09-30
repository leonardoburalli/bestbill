import type { useApiStatus } from '../hooks'
import { formatDate } from '../lib/format'
import { btnPrimary, Notice, Spinner } from './ui'
import { RefreshIcon } from './icons'

type ApiStatusValue = ReturnType<typeof useApiStatus>

/** Stato del servizio: appare solo quando serve dire qualcosa. */
export default function StatusBanner({ api }: { api: ApiStatusValue }) {
  const { status, meta, retry } = api

  if (status === 'checking') {
    return (
      <div role="status" className="flex items-center gap-2.5 rounded-xl border border-line bg-card px-4 py-3 text-[0.95rem] text-ink-soft">
        <Spinner /> Mi collego al servizio…
      </div>
    )
  }

  if (status === 'waking') {
    return (
      <div role="status" className="relative overflow-hidden rounded-xl border border-amber-line bg-amber-soft px-4 py-4 text-[0.95rem]">
        <div className="flex gap-3">
          <span className="mt-1.5 size-3 shrink-0 animate-breathe rounded-full bg-amber-ink" aria-hidden="true" />
          <div>
            <p className="font-semibold text-ink">Il servizio si sta riattivando</p>
            <p className="mt-1 max-w-prose leading-relaxed text-ink-soft">
              BestBill è gratuito e gira su un server che va in pausa quando nessuno lo usa. Riaccenderlo
              richiede di solito 30–60 secondi, solo la prima volta. Nel frattempo puoi già compilare i
              consumi: il calcolo partirà appena il servizio è pronto.
            </p>
          </div>
        </div>
        <div className="mt-3 h-1 overflow-hidden rounded-full bg-amber-line/50" aria-hidden="true">
          <div className="h-full w-1/4 animate-sweep rounded-full bg-amber-ink" />
        </div>
      </div>
    )
  }

  if (status === 'unreachable') {
    return (
      <Notice
        tone="error"
        role="alert"
        title="Non riesco a raggiungere il servizio"
        action={
          <button type="button" onClick={retry} className={btnPrimary}>
            <RefreshIcon size={18} /> Riprova
          </button>
        }
      >
        Dopo oltre un minuto di attesa il server non ha risposto. Controlla la connessione e riprova: se il
        problema continua, potrebbe essere una manutenzione in corso.
      </Notice>
    )
  }

  if (status === 'no-catalog') {
    return (
      <Notice
        tone="warn"
        role="alert"
        title="Il catalogo delle offerte non è ancora disponibile"
        action={
          <button type="button" onClick={retry} className="inline-flex items-center gap-2 rounded-xl border border-field bg-card px-4 py-2.5 font-medium hover:bg-paper-deep">
            <RefreshIcon size={18} /> Controlla di nuovo
          </button>
        }
      >
        Il servizio è acceso ma sta ancora caricando le offerte di oggi. Di solito bastano pochi minuti.
      </Notice>
    )
  }

  if (meta?.stale) {
    return (
      <Notice tone="warn" title="Il catalogo potrebbe non essere aggiornato">
        Le offerte risalgono al {formatDate(meta.snapshot_date)} ({meta.age_days} giorni fa). Alcune potrebbero
        essere cambiate nel frattempo.
      </Notice>
    )
  }

  return null
}
