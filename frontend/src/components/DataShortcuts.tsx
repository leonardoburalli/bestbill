import { useId, useRef, useState } from 'react'
import { api, ApiError } from '../api'
import { parsePastedValues, rowsFromApi } from '../lib/consumption'
import { formatMonthLong, lastCompleteMonth } from '../lib/months'
import type { SampleMonth } from '../types'
import { ClipboardIcon, CloseIcon, HomeIcon, InfoIcon, LockIcon, UploadIcon } from './icons'
import { btnSecondary, inputBase, inputBorder, Notice, Spinner } from './ui'
import { monthAbbrYear, numToText } from './formState'
import type { ConsumptionForm, LoadedFile } from './formState'

type Panel = 'portale' | 'paste' | 'sample' | null

export default function DataShortcuts({ cf }: { cf: ConsumptionForm }) {
  const [open, setOpen] = useState<Panel>(null)

  const tabs: { id: Exclude<Panel, null>; label: string; hint: string; icon: React.ReactNode }[] = [
    { id: 'portale', label: 'Importa da Portale Consumi', hint: 'uno o due file CSV, letti sul tuo dispositivo', icon: <UploadIcon /> },
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
          {open === 'portale' && <PortaleImport cf={cf} />}
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

function coverage(f: LoadedFile): string | null {
  const m = f.parsed?.months
  if (!m || m.length === 0) return null
  const n = m.length
  return `${monthAbbrYear(m[0].month)} – ${monthAbbrYear(m[n - 1].month)}, ${n} ${n === 1 ? 'mese' : 'mesi'}`
}

const linkCls =
  'font-semibold text-forest underline decoration-forest-line decoration-2 underline-offset-2 hover:text-forest-dark'

function PortaleImport({ cf }: { cf: ConsumptionForm }) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [dragging, setDragging] = useState(false)
  const fileId = useId()
  const hintId = useId()
  const { portaleFiles: files, portaleProblem, report } = cf

  const thisYear = new Date().getFullYear()
  const lastYear = thisYear - 1

  const steps: React.ReactNode[] = [
    <>
      Vai su{' '}
      <a href={PORTALE_URL} target="_blank" rel="noopener noreferrer" className={linkCls}>
        Portale Consumi<span className="sr-only"> (si apre in una nuova scheda)</span>
      </a>{' '}
      e accedi con SPID o CIE.
    </>,
    <>Apri la sezione dei consumi di <strong>luce</strong>.</>,
    <>
      Premi <strong>Esporta</strong> per l&apos;anno in corso <strong>e</strong> per quello precedente
      (<strong>{lastYear}</strong> e <strong>{thisYear}</strong>): due file CSV.
    </>,
    <>Caricali qui sotto <strong>insieme</strong>: li uniamo e compiliamo i mesi al posto tuo.</>,
  ]

  const handle = async (list: FileList | File[] | null | undefined) => {
    const picked = list ? Array.from(list) : []
    if (picked.length === 0) return
    setBusy(true)
    try {
      await cf.addPortaleFiles(picked)
    } finally {
      setBusy(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  // Anni che servono ma non sono ancora stati caricati (per il suggerimento accanto alla lista).
  const hasFiles = files.length > 0
  const latestYear = Number(lastCompleteMonth().slice(0, 4))
  const missingYears = (() => {
    if (!report) return [] as number[]
    const need = new Set<number>()
    for (const m of report.missing) need.add(Number(m.slice(0, 4)))
    if (report.last < lastCompleteMonth()) need.add(latestYear)
    return [...need].filter((y) => !report.years.includes(y)).sort((a, b) => a - b)
  })()

  return (
    <div>
      <p className="text-sm font-semibold">Importa i consumi da Portale Consumi</p>
      <p className="mt-0.5 text-sm text-ink-soft">
        Portale Consumi è il sito di Acquirente Unico dove trovi i consumi reali del tuo contatore.
      </p>

      <ol className="mt-3 grid gap-2 sm:grid-cols-2">
        {steps.map((step, i) => (
          <li key={i} className="flex items-start gap-3 rounded-lg border border-line bg-card px-3 py-2.5 text-[0.95rem] leading-snug">
            <span className="mt-px grid size-6 shrink-0 place-items-center rounded-full bg-forest text-xs font-bold text-white tabular">
              {i + 1}
            </span>
            <span>{step}</span>
          </li>
        ))}
      </ol>

      <p className="mt-3 flex items-start gap-2 rounded-lg border border-forest-line bg-forest-soft px-3 py-2.5 text-sm leading-relaxed">
        <span className="mt-0.5 shrink-0 text-forest"><InfoIcon size={16} /></span>
        <span>
          <strong className="font-semibold">Perché due file?</strong> Portale Consumi esporta{' '}
          <strong className="font-semibold">un solo anno di calendario per volta</strong>. Gli ultimi 12 mesi
          di solito stanno a cavallo di due anni (per esempio da settembre {lastYear} ad agosto {thisYear}):
          esporta {lastYear} e {thisYear}, poi caricali entrambi. Puoi sceglierli insieme oppure aggiungerli
          uno alla volta.
        </span>
      </p>

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
          void handle(e.dataTransfer.files)
        }}
        className={`mt-4 flex cursor-pointer flex-col items-center gap-1.5 rounded-xl border-2 border-dashed px-4 py-6 text-center transition-colors has-[:focus-visible]:outline has-[:focus-visible]:outline-[3px] has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-focus ${
          dragging ? 'border-forest bg-forest-soft' : 'border-field bg-card hover:border-forest hover:bg-forest-soft/60'
        }`}
      >
        <span className="text-forest">{busy ? <Spinner size={26} /> : <UploadIcon size={26} />}</span>
        <span className="font-semibold">
          {busy
            ? 'Leggo i file…'
            : hasFiles
              ? 'Aggiungi un altro file CSV o trascinalo qui'
              : 'Scegli i file CSV o trascinali qui'}
        </span>
        <span id={hintId} className="max-w-md text-sm text-ink-soft">
          File .csv fino a 1 MB ciascuno. Puoi sceglierne più di uno.
        </span>
        <input
          ref={fileRef}
          id={fileId}
          type="file"
          multiple
          accept=".csv,text/csv"
          aria-describedby={hintId}
          onChange={(e) => void handle(e.target.files)}
          className="sr-only"
        />
      </label>

      <div aria-live="polite" aria-relevant="additions removals" aria-label="File caricati" className="mt-3">
        {hasFiles && (
          <>
            <p className="text-sm font-semibold">
              {files.length === 1 ? '1 file caricato' : `${files.length} file caricati`}
            </p>
            <ul className="mt-1.5 space-y-1.5">
              {files.map((f) => {
                const cov = coverage(f)
                return (
                  <li
                    key={f.id}
                    className={`flex items-start gap-3 rounded-lg border px-3 py-2 ${
                      f.error ? 'border-brick/40 bg-brick/5' : 'border-line bg-card'
                    }`}
                  >
                    <div className="min-w-0 flex-1">
                      <p className="break-all text-[0.95rem] font-semibold leading-snug">{f.name}</p>
                      {cov ? (
                        <p className="text-sm text-ink-soft">{cov}</p>
                      ) : (
                        <p className="text-sm font-medium text-brick">
                          Non posso usare questo file: {f.error}
                        </p>
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={() => cf.removePortaleFile(f.id)}
                      aria-label={`Rimuovi il file ${f.name}`}
                      className="grid size-9 shrink-0 place-items-center rounded-lg text-ink-soft transition-colors hover:bg-paper hover:text-brick focus-visible:outline focus-visible:outline-[3px] focus-visible:outline-offset-1 focus-visible:outline-focus"
                    >
                      <CloseIcon size={18} />
                    </button>
                  </li>
                )
              })}
            </ul>
          </>
        )}
        {missingYears.length > 0 && (
          <p className="mt-2 text-sm font-medium text-amber-ink">
            {missingYears.map((y) => `Carica anche il file del ${y}`).join(' · ')}: Portale Consumi esporta un anno
            alla volta.
          </p>
        )}
        {portaleProblem && (
          <Notice tone="error" role="alert" title="Non posso usare questi file" className="mt-2">
            {portaleProblem}
          </Notice>
        )}
      </div>

      <p className="mt-3 flex items-start gap-2 text-sm leading-relaxed text-ink-soft">
        <span className="mt-0.5 shrink-0 text-forest"><LockIcon size={16} /></span>
        <span>
          <strong className="font-semibold text-ink">I file restano sul tuo dispositivo.</strong> Li leggiamo
          direttamente nel browser: non vengono caricati né inviati a nessun server.
        </span>
      </p>
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
