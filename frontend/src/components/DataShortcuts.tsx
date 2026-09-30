import { useId, useRef, useState } from 'react'
import { api, ApiError } from '../api'
import { useParseUpload } from '../hooks'
import { parsePastedValues, rowsFromApi } from '../lib/consumption'
import { formatMonthLong } from '../lib/months'
import type { SampleMonth } from '../types'
import { ClipboardIcon, HomeIcon, UploadIcon } from './icons'
import { btnPrimary, btnSecondary, inputBase, inputBorder, Notice, Spinner } from './ui'
import { numToText } from './formState'
import type { ConsumptionForm } from './formState'

type Panel = 'paste' | 'excel' | 'sample' | null

export default function DataShortcuts({ cf }: { cf: ConsumptionForm }) {
  const [open, setOpen] = useState<Panel>(null)

  const tabs: { id: Exclude<Panel, null>; label: string; hint: string; icon: React.ReactNode }[] = [
    { id: 'paste', label: 'Incolla 12 valori', hint: 'da bolletta o foglio di calcolo', icon: <ClipboardIcon /> },
    { id: 'excel', label: 'Carica un file Excel', hint: 'formato .xlsx', icon: <UploadIcon /> },
    { id: 'sample', label: 'Prova con un esempio', hint: 'una famiglia di prova', icon: <HomeIcon /> },
  ]

  return (
    <div>
      <div className="grid gap-2 sm:grid-cols-3" role="group" aria-label="Modi rapidi per inserire i consumi">
        {tabs.map((t) => {
          const active = open === t.id
          return (
            <button
              key={t.id}
              type="button"
              aria-expanded={active}
              aria-controls={`panel-${t.id}`}
              onClick={() => setOpen(active ? null : t.id)}
              className={`flex items-center gap-3 rounded-xl border px-4 py-3 text-left transition-colors ${
                active
                  ? 'border-forest bg-forest-soft'
                  : 'border-line bg-card hover:border-field hover:bg-paper'
              }`}
            >
              <span className="text-forest">{t.icon}</span>
              <span>
                <span className="block text-[0.95rem] font-semibold leading-tight">{t.label}</span>
                <span className="block text-xs text-ink-soft">{t.hint}</span>
              </span>
            </button>
          )
        })}
      </div>

      {open && (
        <div id={`panel-${open}`} className="mt-3 rounded-xl border border-line bg-paper p-4 animate-rise">
          {open === 'paste' && <PasteBox cf={cf} onDone={() => setOpen(null)} />}
          {open === 'excel' && <ExcelUpload cf={cf} onDone={() => setOpen(null)} />}
          {open === 'sample' && <SampleLoader cf={cf} onDone={() => setOpen(null)} />}
        </div>
      )}
    </div>
  )
}

/* ── Incolla ───────────────────────────────────────────────────────────── */

function PasteBox({ cf, onDone }: { cf: ConsumptionForm; onDone: () => void }) {
  const [text, setText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const id = useId()
  const errId = useId()

  const apply = () => {
    const values = parsePastedValues(text)
    if (values.length !== 12) {
      setError(
        values.length === 0
          ? 'Non ho trovato numeri. Incolla 12 valori, uno per mese, separati da a capo, spazio o punto e virgola.'
          : `Ho trovato ${values.length} valori, ne servono esattamente 12 (uno per mese).`,
      )
      return
    }
    if (values.some((v) => v < 0)) {
      setError('I consumi non possono essere negativi.')
      return
    }
    setError(null)
    cf.setCells((cells) => cells.map((c, i) => ({ ...c, kwh: numToText(values[i]) })))
    cf.setNote(`Ho inserito i 12 valori incollati a partire da ${formatMonthLong(cf.form.start)}. Controllali qui sotto.`)
    setText('')
    onDone()
  }

  return (
    <div>
      <label htmlFor={id} className="block text-sm font-semibold">
        Incolla qui i 12 consumi mensili in kWh
      </label>
      <p className="mt-0.5 text-sm text-ink-soft">
        Un valore per mese, dal più vecchio al più recente, a partire da {formatMonthLong(cf.form.start)}. Vanno
        bene i decimali con la virgola (es. 1.234,5).
      </p>
      <textarea
        id={id}
        rows={4}
        value={text}
        onChange={(e) => setText(e.target.value)}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errId : undefined}
        placeholder={'180\n165\n210\n…'}
        className={`${inputBase} ${inputBorder(!!error)} tabular mt-2 font-mono text-sm`}
      />
      {error && (
        <p id={errId} role="alert" className="mt-1.5 text-sm font-medium text-brick">
          {error}
        </p>
      )}
      <button type="button" onClick={apply} className={`${btnSecondary} mt-3`}>
        Inserisci i valori
      </button>
    </div>
  )
}

/* ── Excel ─────────────────────────────────────────────────────────────── */

function ExcelUpload({ cf, onDone }: { cf: ConsumptionForm; onDone: () => void }) {
  const up = useParseUpload()
  const [pick, setPick] = useState(0)
  const fileRef = useRef<HTMLInputElement>(null)
  const legend = useId()
  const fileId = useId()

  const profiles = up.result?.profiles ?? []

  const use = () => {
    const p = profiles[pick]
    if (!p) return
    cf.applyRows(rowsFromApi(p.months), `Consumi caricati dal file Excel (${p.location}). Controllali qui sotto.`)
    up.reset()
    if (fileRef.current) fileRef.current.value = ''
    onDone()
  }

  return (
    <div>
      <label htmlFor={fileId} className="block text-sm font-semibold">
        File Excel con lo storico dei consumi
      </label>
      <p className="mt-0.5 text-sm text-ink-soft">
        File .xlsx fino a 2 MB, con un foglio «Storico_Località» per ogni punto di fornitura. Il file viene
        letto al volo e non viene conservato.
      </p>
      <input
        ref={fileRef}
        id={fileId}
        type="file"
        accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        onChange={(e) => {
          const f = e.target.files?.[0]
          if (f) {
            setPick(0)
            up.upload(f)
          }
        }}
        className="mt-2 block w-full max-w-md cursor-pointer rounded-lg border border-field bg-card text-sm file:mr-3 file:cursor-pointer file:border-0 file:bg-forest file:px-4 file:py-2.5 file:font-semibold file:text-white hover:file:bg-forest-dark"
      />

      <div aria-live="polite" className="mt-3">
        {up.status === 'loading' && (
          <p className="flex items-center gap-2 text-sm text-ink-soft">
            <Spinner /> Leggo il file…
          </p>
        )}
        {up.status === 'error' && up.error && (
          <Notice tone="error" role="alert" title="Non sono riuscito a leggere il file">
            {up.error.status === 429
              ? 'Troppe richieste in poco tempo: aspetta un minuto e riprova.'
              : up.error.fieldErrors[0]?.message ?? up.error.message}
          </Notice>
        )}
        {up.status === 'success' && up.result && (
          <div>
            {profiles.length > 1 ? (
              <fieldset>
                <legend id={legend} className="text-sm font-semibold">
                  Nel file ci sono {profiles.length} punti di fornitura: quale vuoi usare?
                </legend>
                <div className="mt-2 grid gap-2">
                  {profiles.map((p, i) => (
                    <label
                      key={p.location + i}
                      className="flex cursor-pointer items-center gap-3 rounded-lg border border-line bg-card px-3 py-2.5 has-[:checked]:border-forest has-[:checked]:bg-forest-soft"
                    >
                      <input
                        type="radio"
                        name="profile"
                        checked={pick === i}
                        onChange={() => setPick(i)}
                        className="size-4 accent-forest"
                      />
                      <span className="font-medium">{p.location}</span>
                      <span className="text-sm text-ink-soft">
                        {formatMonthLong(p.months[0].month)} – {formatMonthLong(p.months[p.months.length - 1].month)}
                      </span>
                    </label>
                  ))}
                </div>
              </fieldset>
            ) : (
              profiles[0] && (
                <p className="text-sm">
                  Trovato: <strong>{profiles[0].location}</strong>,{' '}
                  {formatMonthLong(profiles[0].months[0].month)} –{' '}
                  {formatMonthLong(profiles[0].months[profiles[0].months.length - 1].month)}.
                </p>
              )
            )}
            {up.result.skipped.length > 0 && (
              <p className="mt-2 text-sm text-ink-soft">
                Non utilizzabili (servono 12 mesi consecutivi): {up.result.skipped.join(', ')}.
              </p>
            )}
            <button type="button" onClick={use} className={`${btnPrimary} mt-3`}>
              Usa questi consumi
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

/* ── Esempio ───────────────────────────────────────────────────────────── */

function SampleLoader({ cf, onDone }: { cf: ConsumptionForm; onDone: () => void }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const s = await api.sample()
      const months: SampleMonth[] = s.months
      cf.applyRows(rowsFromApi(months), `Esempio caricato: ${s.description.replace(/[.\s]+$/, '')}. Puoi modificare i valori.`)
      onDone()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Non riesco a caricare l\'esempio. Riprova.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <p className="text-sm text-ink-soft">
        Carica i consumi di una famiglia di prova per vedere come funziona il confronto. Poi potrai cambiare i
        valori con i tuoi.
      </p>
      <button type="button" onClick={load} disabled={loading} className={`${btnSecondary} mt-3`}>
        {loading ? <Spinner /> : null} {loading ? 'Carico l\'esempio…' : 'Carica l\'esempio'}
      </button>
      {error && (
        <p role="alert" className="mt-2 text-sm font-medium text-brick">
          {error}
        </p>
      )}
    </div>
  )
}
