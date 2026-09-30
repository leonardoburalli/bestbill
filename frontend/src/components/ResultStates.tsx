import type { ApiError } from '../api'
import { ArrowLeftIcon, RefreshIcon } from './icons'
import { btnPrimary, btnSecondary, Notice } from './ui'

export function errorMessage(e: ApiError): { title: string; text: string } {
  if (e.status === 429)
    return {
      title: 'Troppe richieste in poco tempo',
      text: 'Per non sovraccaricare il servizio gratuito c\'è un limite alle richieste. Aspetta circa un minuto e riprova.',
    }
  if (e.status === 0)
    return {
      title: 'Non riesco a raggiungere il servizio',
      text: 'Controlla la connessione. Se il servizio era in pausa, può servire un minuto per riattivarsi: riprova tra poco.',
    }
  if (e.status === 503)
    return {
      title: 'Il catalogo delle offerte non è disponibile',
      text: 'Il servizio sta caricando le offerte. Riprova tra qualche minuto.',
    }
  if (e.status === 422)
    return { title: 'Alcuni dati non sono validi', text: e.fieldErrors.map((f) => f.message).join(' ') || e.message }
  if (e.status >= 500)
    return { title: 'Il servizio ha avuto un problema', text: 'Non è colpa dei tuoi dati. Riprova tra poco.' }
  return { title: 'Non sono riuscito a completare il confronto', text: e.message }
}

export function ResultsSkeleton({ slow }: { slow: boolean }) {
  return (
    <div className="space-y-5" aria-hidden={false}>
      <div role="status" className="rounded-2xl border border-line bg-card p-6">
        <div className="flex items-center gap-3">
          <span className="size-3 animate-breathe rounded-full bg-forest" aria-hidden="true" />
          <p className="font-display text-xl font-semibold">Sto confrontando le offerte…</p>
        </div>
        <p className="mt-2 max-w-prose leading-relaxed text-ink-soft">
          {slow
            ? 'Ci sta mettendo più del solito: il servizio gratuito era in pausa e si sta riattivando. Di solito bastano 30–60 secondi, poi il calcolo è rapido. Non chiudere la pagina.'
            : 'Calcolo quanto spenderesti nei prossimi 12 mesi con ogni offerta, se consumassi come nel periodo indicato. Dovrebbero bastare pochi secondi.'}
        </p>
        <div className="mt-4 h-1 overflow-hidden rounded-full bg-paper-deep">
          <div className="h-full w-1/4 animate-sweep rounded-full bg-forest" />
        </div>
      </div>
      <div className="h-36 animate-pulse rounded-2xl bg-paper-deep/70" />
      <div className="space-y-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-24 animate-pulse rounded-2xl bg-paper-deep/50" />
        ))}
      </div>
    </div>
  )
}

export function ResultsError({
  error,
  onRetry,
  onBack,
}: {
  error: ApiError
  onRetry: () => void
  onBack: () => void
}) {
  const { title, text } = errorMessage(error)
  return (
    <Notice
      tone="error"
      role="alert"
      title={title}
      action={
        <>
          <button type="button" onClick={onRetry} className={btnPrimary}>
            <RefreshIcon size={18} /> Riprova
          </button>
          <button type="button" onClick={onBack} className={btnSecondary}>
            <ArrowLeftIcon size={18} /> Modifica i consumi
          </button>
        </>
      }
    >
      {text}
    </Notice>
  )
}
