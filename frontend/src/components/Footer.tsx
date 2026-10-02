import type { CatalogMeta } from '../types'
import { formatDate } from '../lib/format'

export default function Footer({ meta }: { meta: CatalogMeta | null }) {
  return (
    <footer className="mt-16 border-t border-line bg-paper-deep/60">
      <div className="mx-auto grid max-w-5xl gap-8 px-4 py-10 text-sm leading-relaxed text-ink-soft sm:px-6 md:grid-cols-3">
        <section aria-labelledby="f-dati">
          <h2 id="f-dati" className="mb-2 font-display text-base font-semibold text-ink">
            Da dove vengono i dati
          </h2>
          <p>
            Le offerte arrivano dal Portale Offerte di ARERA (PLACET e mercato libero).
            {meta?.snapshot_date && <> Ultimo aggiornamento: {formatDate(meta.snapshot_date)}.</>} I prezzi
            all'ingrosso (PUN) sono quelli pubblicati mese per mese.
          </p>
          {meta?.attribution && <p className="mt-2">{meta.attribution}</p>}
          {meta && meta.sources.length > 0 && (
            <ul className="mt-2 list-disc space-y-0.5 pl-5">
              {meta.sources.map((s) => (
                <li key={s.name}>
                  {s.url && /^https?:\/\//i.test(s.url) ? (
                    <a href={s.url} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 hover:text-ink">
                      {s.name}
                    </a>
                  ) : (
                    s.name
                  )}
                  {s.file_date ? ` (${formatDate(s.file_date)})` : ''}
                </li>
              ))}
            </ul>
          )}
          <p className="mt-2 text-xs text-ink-soft/80">Versione v{__APP_VERSION__}</p>
        </section>

        <section aria-labelledby="f-licenza">
          <h2 id="f-licenza" className="mb-2 font-display text-base font-semibold text-ink">
            Licenze e limiti
          </h2>
          <p>
            Dati elaborati con licenza CC BY-SA 4.0. Codice del sito con licenza MIT. BestBill è un progetto
            indipendente, non collegato ad ARERA né ai fornitori.
          </p>
          <p className="mt-2">
            Il confronto riguarda solo la materia energia: non include IVA, costi di rete, oneri di sistema e
            imposte, uguali per tutte le offerte. È una simulazione dei prossimi 12 mesi che parte dai tuoi consumi passati: non è una previsione.
          </p>
        </section>

        <section aria-labelledby="f-privacy">
          <h2 id="f-privacy" className="mb-2 font-display text-base font-semibold text-ink">
            Privacy
          </h2>
          <p>
            I consumi che inserisci vengono usati in memoria per fare il calcolo e non vengono salvati né
            registrati. Il file CSV di Portale Consumi viene letto nel tuo browser e non lascia il tuo dispositivo. Il sito non usa cookie né strumenti di analisi e non richiede registrazione.
          </p>
        </section>
      </div>
    </footer>
  )
}
