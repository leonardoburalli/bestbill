/**
 * Footer: attribution, privacy, snapshot info.
 */
import type { CatalogMeta } from '../types'

interface Props {
  meta: CatalogMeta | null
}

export default function Footer({ meta }: Props) {
  return (
    <footer className="max-w-4xl mx-auto px-4 py-6 border-t border-border">
      <div className="space-y-2 text-xs text-text-muted">
        {meta && (
          <p>
            Dati: {meta.sources.map((s) => s.name).join(' · ')}
            {meta.licence && ` · Licenza ${meta.licence}`}
          </p>
        )}
        {meta?.attribution && (
          <p>{meta.attribution}</p>
        )}
        <p>
          BestBill confronta solo il <strong>costo materia energia (IVA esclusa)</strong>.
          I costi di rete, gli oneri di sistema e le imposte sono uguali per ogni offerta e non sono inclusi.
        </p>
        <p>
          Snapshot: {meta?.snapshot_date ? new Date(meta.snapshot_date).toLocaleDateString('it-IT') : '—'}
          {meta?.stale ? ' (aggiorna il catalogo)' : ''}
        </p>
        <p className="pt-2">
          Codice: MIT · <a href="https://github.com/leonardoburalli/bestbill" className="text-brand hover:text-brand-dark">GitHub</a>
        </p>
      </div>
    </footer>
  )
}
