import { useId } from 'react'
import { POWER_MAX } from '../lib/consumption'
import type { useComuniSearch } from '../hooks'
import ComuneField from './ComuneField'
import { FieldError, inputBase, inputBorder } from './ui'
import type { ConsumptionForm } from './formState'

export default function HouseholdFields({
  cf,
  search,
}: {
  cf: ConsumptionForm
  search: ReturnType<typeof useComuniSearch>
}) {
  const { form, patch, check, mapped, attempted } = cf
  const powerId = useId()
  const powerHelp = useId()
  const powerErrId = useId()
  const powerErr = mapped.power ?? (attempted || form.power !== '3' ? check.power : undefined)

  return (
    <div className="grid gap-6 md:grid-cols-2">
      <div className="md:col-span-2">
        <ComuneField search={search} error={mapped.comune} />
      </div>

      <fieldset>
        <legend className="mb-1.5 text-sm font-semibold">Tipo di utenza</legend>
        <div className="grid gap-2">
          {(
            [
              ['resident', 'Residente', 'Prima casa, dove hai la residenza'],
              ['non_resident', 'Non residente', 'Seconda casa o altro uso'],
            ] as const
          ).map(([value, label, hint]) => (
            <label
              key={value}
              className="flex cursor-pointer items-start gap-3 rounded-xl border border-line bg-card px-3.5 py-3 has-[:checked]:border-forest has-[:checked]:bg-forest-soft"
            >
              <input
                type="radio"
                name="residency"
                value={value}
                checked={form.residency === value}
                onChange={() => patch({ residency: value })}
                className="mt-1 size-4 accent-forest"
              />
              <span>
                <span className="block font-medium">{label}</span>
                <span className="block text-sm text-ink-soft">{hint}</span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      <div>
        <label htmlFor={powerId} className="mb-1.5 block text-sm font-semibold">
          Potenza impegnata
        </label>
        <div className="relative max-w-[12rem]">
          <input
            id={powerId}
            type="text"
            inputMode="decimal"
            autoComplete="off"
            value={form.power}
            onChange={(e) => patch({ power: e.target.value })}
            aria-invalid={powerErr ? true : undefined}
            aria-describedby={`${powerHelp}${powerErr ? ' ' + powerErrId : ''}`}
            className={`${inputBase} ${inputBorder(!!powerErr)} tabular pr-12 text-right`}
          />
          <span aria-hidden="true" className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm text-ink-soft">
            kW
          </span>
        </div>
        <p id={powerHelp} className="mt-1.5 text-sm text-ink-soft">
          La trovi in bolletta. In una casa è quasi sempre 3 kW; puoi indicare fino a {POWER_MAX} kW.
        </p>
        {powerErr && <FieldError id={powerErrId}>{powerErr}</FieldError>}
      </div>
    </div>
  )
}
