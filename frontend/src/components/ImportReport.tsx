import { formatMonthLong, lastCompleteMonth } from '../lib/months'
import { AlertIcon, CheckIcon } from './icons'
import { btnSecondary } from './ui'
import type { ImportReport as Report } from './formState'

/**
 * Cosa è successo dopo l'importazione da Portale Consumi.
 * `absent` = mesi del periodo scelto che non sono nel file; `pending` = quelli tra questi ancora vuoti.
 * Si aggiorna mentre si compila o si sposta il periodo.
 */
export default function ImportReport({
  report,
  absent,
  pending,
}: {
  report: Report
  absent: string[]
  pending: string[]
}) {
  const { warnings, totalMonths, first, last, files, years } = report
  const source = files.length === 1 ? `«${files[0].name}»` : `${files.length} file`
  const containers = files.length === 1 ? 'contiene' : 'contengono'
  // Anni dei mesi ancora vuoti che nessun file copre: probabilmente manca il file di quell'anno.
  const missingYears = [...new Set(pending.map((m) => Number(m.slice(0, 4))))]
    .filter((y) => !years.includes(y))
    .sort((a, b) => a - b)
  // Periodo completo ma non aggiornato: i file non arrivano fino all'ultimo mese concluso.
  const newestYear = Number(lastCompleteMonth().slice(0, 4))
  const stale = last < lastCompleteMonth() && !years.includes(newestYear)
  const fromFile = 12 - absent.length
  const partial = absent.length > 0
  const filledByHand = absent.length - pending.length

  const goToFirst = () => {
    // Le righe evidenziate portano l'indice del mese: si prende la prima ancora vuota.
    const idx = document.querySelector('[data-not-in-file="true"]')?.getAttribute('data-idx')
    if (idx) document.getElementById(`kwh-${idx}`)?.focus()
  }

  return (
    <div className="mt-4 space-y-2.5">
      <div
        role="status"
        className={`flex gap-3 rounded-xl border px-4 py-3.5 text-[0.95rem] leading-relaxed ${
          pending.length > 0 ? 'border-amber-line bg-amber-soft' : 'border-forest-line bg-forest-soft'
        }`}
      >
        <span className={`mt-0.5 shrink-0 ${pending.length > 0 ? 'text-amber-ink' : 'text-forest'}`}>
          {pending.length > 0 ? <AlertIcon size={20} /> : <CheckIcon size={20} />}
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-semibold">
            {partial
              ? `Il file copre ${fromFile} mesi su 12 del periodo scelto`
              : `Importati tutti i 12 mesi da ${source}`}
          </p>
          <p className="text-ink-soft">
            {source.charAt(0).toUpperCase() + source.slice(1)} {containers} {totalMonths} {totalMonths === 1 ? 'mese' : 'mesi'}, da{' '}
            {formatMonthLong(first)} a {formatMonthLong(last)}. Ho scelto l'ultimo periodo di 12 mesi già concluso
            (il mese in corso non si può usare).
            {totalMonths > 12 && ' Per usare altri mesi, cambia il periodo qui sotto: i valori si aggiornano da soli.'}
          </p>

          {partial && (
            <div className="mt-2 border-t border-amber-line/70 pt-2">
              {pending.length > 0 ? (
                <>
                  {missingYears.length > 0 && (
                    <p className="mb-2 rounded-lg border border-amber-line bg-card px-3 py-2">
                      <strong className="font-semibold">
                        {missingYears.map((y) => `Carica anche il file del ${y}`).join(' e ')}.
                      </strong>{' '}
                      Portale Consumi esporta un anno di calendario per volta: i mesi che mancano sono del{' '}
                      {missingYears.join(' e ')}. Aggiungi il file qui sopra e li compiliamo noi.
                    </p>
                  )}
                  <p>
                    <strong className="font-semibold">
                      {pending.length === 1 ? 'Manca 1 mese' : `Mancano ${pending.length} mesi`} da compilare:
                    </strong>{' '}
                    {pending.map(formatMonthLong).join(', ')}.
                  </p>
                  <p className="mt-1 text-ink-soft">
                    Sono evidenziati in giallo qui sotto: scrivi tu i kWh (per esempio dalla bolletta), oppure
                    sposta il periodo con «Da» e «A» per usare mesi che hai già. Servono tutti e 12 i mesi.
                  </p>
                  <button type="button" onClick={goToFirst} className={`${btnSecondary} mt-2.5`}>
                    Vai al primo mese mancante
                  </button>
                </>
              ) : (
                <p>
                  <strong className="font-semibold text-forest-dark">Ora i 12 mesi sono completi.</strong> Hai scritto
                  tu {filledByHand === 1 ? '1 mese' : `${filledByHand} mesi`} che non erano nel file.
                </p>
              )}
            </div>
          )}

          {!partial && stale && (
            <p className="mt-2 border-t border-forest-line pt-2">
              <strong className="font-semibold">Carica anche il file del {newestYear}</strong> se vuoi i consumi più
              recenti: i file arrivano fino a {formatMonthLong(last)}, ma l'ultimo mese concluso è{' '}
              {formatMonthLong(lastCompleteMonth())}. Portale Consumi esporta un anno per volta.
            </p>
          )}
        </div>
      </div>

      {warnings.length > 0 && (
        <div role="status" className="flex gap-3 rounded-xl border border-amber-line bg-amber-soft px-4 py-3.5 text-[0.95rem] leading-relaxed">
          <span className="mt-0.5 shrink-0 text-amber-ink"><AlertIcon size={20} /></span>
          <div className="min-w-0">
            <p className="font-semibold">Da sapere</p>
            <ul className="mt-0.5 list-disc space-y-1 pl-5 text-ink-soft">
              {warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  )
}
