import { useId } from 'react'
import { CloseIcon, SearchIcon } from './icons'
import { inputBase, inputBorder } from './ui'

/** "Cerca fornitore o offerta". The parent debounces; clearing is immediate. */
export default function SearchBox({
  value,
  busy,
  onChange,
}: {
  value: string
  busy?: boolean
  onChange: (v: string) => void
}) {
  const id = useId()
  const helpId = useId()
  return (
    <div role="search">
      <label htmlFor={id} className="mb-1.5 block text-sm font-semibold">
        Cerca fornitore o offerta
      </label>
      <div className="relative max-w-xl">
        <span aria-hidden="true" className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-ink-soft">
          <SearchIcon size={18} />
        </span>
        <input
          id={id}
          type="text"
          value={value}
          maxLength={100}
          autoComplete="off"
          enterKeyHint="search"
          placeholder="Per esempio: Plenitude, Fixa Time…"
          aria-describedby={helpId}
          aria-busy={busy || undefined}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Escape' && value) onChange('')
          }}
          className={`${inputBase} ${inputBorder(false)} pl-10 ${value ? 'pr-11' : ''}`}
        />
        {value && (
          <button
            type="button"
            onClick={() => onChange('')}
            className="absolute inset-y-0 right-1.5 my-auto flex size-9 items-center justify-center rounded-lg text-ink-soft transition-colors hover:bg-paper-deep hover:text-ink"
          >
            <CloseIcon size={18} />
            <span className="sr-only">Cancella la ricerca</span>
          </button>
        )}
      </div>
      <p id={helpId} className="mt-1.5 text-[0.8rem] leading-snug text-ink-soft">
        La posizione e la differenza restano quelle dell'elenco completo, con i tuoi filtri.
      </p>
    </div>
  )
}
