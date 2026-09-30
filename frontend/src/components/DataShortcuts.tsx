import { useId, useRef, useState } from 'react'
import { api, ApiError } from '../api'
import { parsePastedValues, rowsFromApi } from '../lib/consumption'
import { PortaleConsumiError, readPortaleConsumiFile } from '../lib/portaleConsumi'
import { formatMonthLong } from '../lib/months'
import type { SampleMonth } from '../types'
import { ClipboardIcon, HomeIcon, LockIcon, UploadIcon } from './icons'
import { btnSecondary, inputBase, inputBorder, Notice, Spinner } from './ui'
import { numToText } from './formState'
import type { ConsumptionForm } from './formState'

type Panel = 'portale' | 'paste' | 'sample' | null

export default function DataShortcuts({ cf }: { cf: ConsumptionForm }) {
  const [open, setOpen] = useState<Panel>(null)

  const tabs: { id: Exclude<Panel, null>; label: string; hint: string; icon: React.ReactNode }[] = [
    { id: 'portale', label: 'Importa da Portale Consumi', hint: 'file CSV, letto sul tuo dispositivo', icon: <UploadIcon /> },
    { id: 'paste', label: 'Incolla 12 valori', hint: 'da bolletta o foglio di calcolo', icon: <ClipboardIcon /> },
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
          {open === 'portale' && <PortaleImport cf={cf} onDone={() => setOpen(null)} />}
          {open === 'paste' && <PasteBox cf={cf} onDone={() => setOpen(null)} />}
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
    cf.forgetImport()
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

/* ── Portale Consumi ───────────────────────────────────────────────────── */

const PORTALE_URL = 'https://www.consumienergia.it'

const STEPS: React.ReactNode[] = [
  <>
    Vai su{' '}
    <a href={PORTALE_URL} target="_blank" rel="noopener noreferrer" className="font-semibold text-forest underline decoration-forest-line decoration-2 underline-offset-2 hover:text-forest-dark">
      Portale Consumi<span className="sr-only"> (si apre in una nuova scheda)</span>
    </a>{' '}
    e accedi con SPID o CIE.
  </>,
  <>Apri la sezione dei consumi di <strong>luce</strong>.</>,
  <>Scarica o esporta lo storico in formato <strong>CSV</strong>.</>,
  <>Caricalo qui sotto: ti compiliamo i mesi al posto tuo.</>,
]

function PortaleImport({ cf, onDone }: { cf: ConsumptionForm; onDone: () => void }) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)
  const fileId = useId()
  const hintId = useId()

  const handle = async (file: File | undefined) => {
    if (!file) return
    setBusy(true)
    setError(null)
    try {
      const parsed = await readPortaleConsumiFile(file)
      const problem = cf.importPortale(parsed, file.name)
      if (problem) {
        setError(problem)
      } else {
        onDone()
      }
    } catch (e) {
      setError(
        e instanceof PortaleConsumiError
          ? e.message
          : 'Non sono riuscito a leggere il file. Controlla che sia il CSV scaricato da Portale Consumi.',
      )
    } finally {
      setBusy(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  return (
    <div>
      <p className="text-sm font-semibold">Importa i consumi da Portale Consumi</p>
      <p className="mt-0.5 text-sm text-ink-soft">
        Portale Consumi è il sito di Acquirente Unico dove trovi i consumi reali del tuo contatore.
      </p>

      <ol className="mt-3 grid gap-2 sm:grid-cols-2">
        {STEPS.map((step, i) => (
          <li key={i} className="flex items-start gap-3 rounded-lg border border-line bg-card px-3 py-2.5 text-[0.95rem] leading-snug">
            <span className="mt-px grid size-6 shrink-0 place-items-center rounded-full bg-forest text-xs font-bold text-white tabular">
              {i + 1}
            </span>
            <span>{step}</span>
          </li>
        ))}
      </ol>

      <label
        htmlFor={fileId}
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          void handle(e.dataTransfer.files?.[0])
        }}
        className={`mt-4 flex cursor-pointer flex-col items-center gap-1.5 rounded-xl border-2 border-dashed px-4 py-6 text-center transition-colors has-[:focus-visible]:outline has-[:focus-visible]:outline-[3px] has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-focus ${
          dragging ? 'border-forest bg-forest-soft' : 'border-field bg-card hover:border-forest hover:bg-forest-soft/60'
        }`}
      >
        <span className="text-forest">{busy ? <Spinner size={26} /> : <UploadIcon size={26} />}</span>
        <span className="font-semibold">{busy ? 'Leggo il file…' : 'Scegli il file CSV o trascinalo qui'}</span>
        <span id={hintId} className="max-w-md text-sm text-ink-soft">
          File .csv fino a 1 MB.
        </span>
        <input
          ref={fileRef}
          id={fileId}
          type="file"
          accept=".csv,text/csv"
          aria-describedby={hintId}
          onChange={(e) => void handle(e.target.files?.[0])}
          className="sr-only"
        />
      </label>

      <p className="mt-3 flex items-start gap-2 text-sm leading-relaxed text-ink-soft">
        <span className="mt-0.5 shrink-0 text-forest"><LockIcon size={16} /></span>
        <span>
          <strong className="font-semibold text-ink">Il file resta sul tuo dispositivo.</strong> Lo leggiamo
          direttamente nel browser: non viene caricato né inviato a nessun server.
        </span>
      </p>

      <div aria-live="polite" className="mt-3">
        {error && (
          <Notice tone="error" role="alert" title="Non posso usare questo file">
            {error}
          </Notice>
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
