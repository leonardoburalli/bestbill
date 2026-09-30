import { useEffect, useId, useRef, useState } from 'react'
import type { useComuniSearch } from '../hooks'
import { CloseIcon, SearchIcon } from './icons'
import { FieldError, inputBase, inputBorder, Spinner } from './ui'
import { comuneLabel } from './formState'

type Search = ReturnType<typeof useComuniSearch>

/** Campo con suggerimenti (pattern ARIA "combobox" con lista). */
export default function ComuneField({ search, error }: { search: Search; error?: string }) {
  const { query, setQuery, results, loading, selected, select, clear } = search
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const inputRef = useRef<HTMLInputElement>(null)
  const inputId = useId()
  const listId = useId()
  const helpId = useId()
  const errId = useId()

  const canSearch = query.trim().length >= 2 && !selected
  const showList = open && canSearch && results.length > 0
  const showEmpty = open && canSearch && !loading && results.length === 0

  useEffect(() => setActive(-1), [results])

  const choose = (i: number) => {
    const c = results[i]
    if (!c) return
    select(c)
    setOpen(false)
    setActive(-1)
  }

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      if (!open) setOpen(true)
      if (results.length) setActive((a) => (a + 1) % results.length)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      if (results.length) setActive((a) => (a <= 0 ? results.length - 1 : a - 1))
    } else if (e.key === 'Enter') {
      if (showList && active >= 0) {
        e.preventDefault()
        choose(active)
      }
    } else if (e.key === 'Escape') {
      if (open) {
        e.preventDefault()
        setOpen(false)
        setActive(-1)
      }
    }
  }

  return (
    <div className="relative">
      <label htmlFor={inputId} className="mb-1.5 block text-sm font-semibold">
        Comune di fornitura <span className="font-normal text-ink-soft">(facoltativo)</span>
      </label>
      <div className="relative">
        <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-ink-soft">
          <SearchIcon size={18} />
        </span>
        <input
          ref={inputRef}
          id={inputId}
          type="text"
          role="combobox"
          autoComplete="off"
          spellCheck={false}
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={showList && active >= 0 ? `${listId}-${active}` : undefined}
          aria-describedby={`${helpId}${error ? ' ' + errId : ''}`}
          aria-invalid={error ? true : undefined}
          value={query}
          placeholder="Scrivi le prime lettere, es. Bologna"
          onChange={(e) => {
            setQuery(e.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          onKeyDown={onKeyDown}
          className={`${inputBase} ${inputBorder(!!error)} pl-10 ${query ? 'pr-20' : ''}`}
        />
        <div className="absolute inset-y-0 right-2 flex items-center gap-1">
          {loading && canSearch && (
            <span className="text-ink-soft">
              <Spinner size={16} />
              <span className="sr-only">Cerco…</span>
            </span>
          )}
          {query && (
            <button
              type="button"
              onClick={() => {
                clear()
                inputRef.current?.focus()
              }}
              className="grid size-8 place-items-center rounded-md text-ink-soft hover:bg-paper-deep"
              aria-label="Cancella il comune"
            >
              <CloseIcon size={16} />
            </button>
          )}
        </div>
      </div>

      {showList && (
        <ul
          id={listId}
          role="listbox"
          aria-label="Comuni suggeriti"
          className="absolute z-20 mt-1 max-h-64 w-full overflow-auto rounded-xl border border-field bg-card py-1 shadow-lg"
        >
          {results.map((c, i) => (
            <li
              key={c.codice}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => choose(i)}
              onMouseMove={() => setActive(i)}
              className={`flex cursor-pointer items-baseline justify-between gap-3 px-3.5 py-2.5 ${
                i === active ? 'bg-forest-soft' : ''
              }`}
            >
              <span className="font-medium">{comuneLabel(c)}</span>
              <span className="text-sm text-ink-soft">{c.regione}</span>
            </li>
          ))}
        </ul>
      )}

      <div aria-live="polite" className="text-sm">
        {showEmpty && <p className="mt-1.5 text-ink-soft">Nessun comune trovato. Controlla come l'hai scritto.</p>}
        {selected && (
          <p className="mt-1.5 font-medium text-forest">
            Selezionato: {comuneLabel(selected)}, {selected.regione}
          </p>
        )}
      </div>
      <p id={helpId} className="mt-1 text-sm text-ink-soft">
        Serve solo per includere le offerte valide in specifiche zone. Senza comune vedrai le offerte disponibili
        ovunque.
      </p>
      {error && <FieldError id={errId}>{error}</FieldError>}
    </div>
  )
}
