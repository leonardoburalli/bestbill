import { useId } from 'react'
import { buildMonths, formatMonthLong, monthOptions } from '../lib/months'
import { parsePastedValues } from '../lib/consumption'
import { formatKwh } from '../lib/format'
import { CheckIcon } from './icons'
import { FieldError, inputBase, inputBorder } from './ui'
import { numToText } from './formState'
import type { CellField, ConsumptionForm } from './formState'

const BAND_FIELDS: { key: 'f1' | 'f2' | 'f3'; label: string }[] = [
  { key: 'f1', label: 'F1' },
  { key: 'f2', label: 'F2' },
  { key: 'f3', label: 'F3' },
]

export default function MonthGrid({ cf }: { cf: ConsumptionForm }) {
  const { form, check, mapped, attempted, patch, setCell, setCells } = cf
  const months = buildMonths(form.start)
  const selectId = useId()
  const bandsHelpId = useId()

  const opts = monthOptions()
  if (!opts.includes(form.start)) opts.push(form.start)
  opts.sort().reverse()

  const focusField = (i: number, f: CellField) =>
    document.getElementById(`${f}-${i}`)?.focus()

  const onPaste = (i: number, field: CellField, e: React.ClipboardEvent<HTMLInputElement>) => {
    const values = parsePastedValues(e.clipboardData.getData('text'))
    if (values.length < 2) return
    e.preventDefault()
    setCells((cells) =>
      cells.map((c, j) => (j >= i && j - i < values.length ? { ...c, [field]: numToText(values[j - i]) } : c)),
    )
  }

  const last = months[11]

  return (
    <div>
      <div className="flex flex-wrap items-end gap-x-6 gap-y-3">
        <div>
          <label htmlFor={selectId} className="mb-1.5 block text-sm font-semibold">
            Periodo dei 12 mesi
          </label>
          <select
            id={selectId}
            value={form.start}
            onChange={(e) => patch({ start: e.target.value })}
            className={`${inputBase} ${inputBorder(false)} min-w-[16rem] pr-8`}
          >
            {opts.map((ym) => {
              const end = buildMonths(ym)[11]
              return (
                <option key={ym} value={ym}>
                  da {formatMonthLong(ym)} a {formatMonthLong(end)}
                </option>
              )
            })}
          </select>
        </div>
        <p className="pb-2.5 text-sm text-ink-soft">
          Mese per mese, da <strong className="font-semibold text-ink">{formatMonthLong(form.start)}</strong> a{' '}
          <strong className="font-semibold text-ink">{formatMonthLong(last)}</strong>.
        </p>
      </div>

      <label className="mt-5 flex cursor-pointer items-start gap-3 rounded-xl border border-line bg-paper px-4 py-3">
        <input
          type="checkbox"
          checked={form.useBands}
          onChange={(e) => patch({ useBands: e.target.checked })}
          aria-describedby={bandsHelpId}
          className="mt-1 size-5 shrink-0 accent-forest"
        />
        <span>
          <span className="block font-semibold">Ho anche i kWh per fascia (F1, F2, F3)</span>
          <span id={bandsHelpId} className="block text-sm leading-relaxed text-ink-soft">
            Facoltativo. Li trovi in bolletta. Se non li indichi, usiamo una ripartizione standard tra le
            fasce. Se li indichi, serve compilarli per tutti i 12 mesi.
          </span>
        </span>
      </label>

      <ol
        className={`mt-5 grid gap-x-8 gap-y-3 ${
          form.useBands ? '' : 'md:grid-flow-col md:grid-rows-6'
        }`}
      >
        {months.map((ym, i) => {
          const c = form.cells[i]
          const fb = check.rows[i]
          const srv = mapped.rows[i]
          const kwhMsg = srv?.kwh ?? ((attempted || fb.kwhTouched) ? fb.kwh : undefined)
          const bandsMsg =
            srv?.bands ?? srv?.general ?? ((attempted || fb.bandsTouched) && form.useBands ? fb.bands : undefined)
          const kwhErrId = `kwh-${i}-err`
          const bandsErrId = `bands-${i}-err`
          const label = formatMonthLong(ym)
          return (
            <li
              key={ym}
              className={`grid items-start gap-x-3 gap-y-2 ${
                form.useBands ? 'grid-cols-[8.5rem_1fr] sm:grid-cols-[9.5rem_11rem_1fr]' : 'grid-cols-[8.5rem_1fr]'
              }`}
            >
              <label htmlFor={`kwh-${i}`} className="pt-2.5 font-medium first-letter:uppercase">
                {label}
              </label>
              <div>
                <div className="relative">
                  <input
                    id={`kwh-${i}`}
                    type="text"
                    inputMode="decimal"
                    autoComplete="off"
                    value={c.kwh}
                    onChange={(e) => setCell(i, 'kwh', e.target.value)}
                    onPaste={(e) => onPaste(i, 'kwh', e)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault()
                        if (i < 11) focusField(i + 1, 'kwh')
                      }
                    }}
                    aria-invalid={kwhMsg ? true : undefined}
                    aria-describedby={kwhMsg ? kwhErrId : undefined}
                    className={`${inputBase} ${inputBorder(!!kwhMsg)} tabular pr-12 text-right`}
                  />
                  <span aria-hidden="true" className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm text-ink-soft">
                    kWh
                  </span>
                </div>
                {kwhMsg && <FieldError id={kwhErrId}>{kwhMsg}</FieldError>}
              </div>

              {form.useBands && (
                <div className="col-span-full sm:col-span-1">
                  <div className="grid grid-cols-3 gap-2">
                    {BAND_FIELDS.map(({ key, label: bl }) => (
                      <div key={key} className="relative">
                        <input
                          id={`${key}-${i}`}
                          type="text"
                          inputMode="decimal"
                          autoComplete="off"
                          value={c[key]}
                          onChange={(e) => setCell(i, key, e.target.value)}
                          onPaste={(e) => onPaste(i, key, e)}
                          aria-label={`${bl} di ${label}, in kWh`}
                          aria-invalid={bandsMsg ? true : undefined}
                          aria-describedby={bandsMsg ? bandsErrId : undefined}
                          className={`${inputBase} ${inputBorder(!!bandsMsg)} tabular pt-5 pb-1.5 text-right`}
                        />
                        <span aria-hidden="true" className="pointer-events-none absolute left-3 top-1.5 text-xs font-semibold text-ink-soft">
                          {bl}
                        </span>
                      </div>
                    ))}
                  </div>
                  {bandsMsg ? (
                    <FieldError id={bandsErrId}>{bandsMsg}</FieldError>
                  ) : fb.bandsOk && fb.bandSum !== null ? (
                    <p className="mt-1.5 flex items-center gap-1.5 text-sm font-medium text-forest">
                      <CheckIcon size={16} /> Somma fasce {formatKwh(fb.bandSum)}: coincide con il mese.
                    </p>
                  ) : fb.bandSum !== null ? (
                    <p className="mt-1.5 text-sm text-ink-soft">Somma fasce: {formatKwh(fb.bandSum)}</p>
                  ) : null}
                </div>
              )}
            </li>
          )
        })}
      </ol>

      <p className="mt-5 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-t border-dashed border-line pt-4 text-sm text-ink-soft" aria-live="polite">
        <span>
          Mesi compilati: <strong className="tabular text-ink">{check.filled}</strong> su 12. Puoi scrivere 0 per un
          mese senza consumi.
        </span>
        <span>
          Totale: <strong className="tabular text-base text-ink">{formatKwh(check.totalKwh)}</strong>
        </span>
      </p>
    </div>
  )
}
