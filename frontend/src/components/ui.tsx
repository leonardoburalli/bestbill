import type { ReactNode } from 'react'
import { AlertIcon, InfoIcon } from './icons'

export const btnPrimary =
  'inline-flex items-center justify-center gap-2 rounded-xl bg-forest px-5 py-3 text-base font-semibold text-white shadow-sm transition-colors hover:bg-forest-dark disabled:cursor-not-allowed disabled:bg-[#6d7f76] disabled:shadow-none'

export const btnSecondary =
  'inline-flex items-center justify-center gap-2 rounded-xl border border-field bg-card px-4 py-2.5 text-[0.95rem] font-medium text-ink transition-colors hover:bg-paper-deep disabled:cursor-not-allowed disabled:opacity-60'

export const btnQuiet =
  'inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-[0.95rem] font-medium text-forest underline decoration-forest-line decoration-2 underline-offset-4 transition-colors hover:bg-forest-soft'

export const inputBase =
  'w-full rounded-lg border bg-card px-3 py-2.5 text-base text-ink placeholder:text-ink-soft/70 shadow-[inset_0_1px_2px_rgb(24_37_31/0.06)] disabled:bg-paper-deep'

export const inputBorder = (invalid: boolean) =>
  invalid ? 'border-brick border-2' : 'border-field'

export function Spinner({ size = 18 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      className="animate-spin"
      aria-hidden="true"
      focusable="false"
    >
      <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  )
}

type Tone = 'info' | 'warn' | 'error' | 'ok'

const toneClass: Record<Tone, string> = {
  info: 'border-forest-line bg-forest-soft text-ink',
  ok: 'border-forest-line bg-forest-soft text-ink',
  warn: 'border-amber-line bg-amber-soft text-ink',
  error: 'border-brick-line bg-brick-soft text-ink',
}
const toneIcon: Record<Tone, string> = {
  info: 'text-forest',
  ok: 'text-forest',
  warn: 'text-amber-ink',
  error: 'text-brick',
}

export function Notice({
  tone = 'info',
  title,
  children,
  action,
  role,
  className = '',
}: {
  tone?: Tone
  title?: string
  children?: ReactNode
  action?: ReactNode
  role?: 'alert' | 'status'
  className?: string
}) {
  const Icon = tone === 'warn' || tone === 'error' ? AlertIcon : InfoIcon
  return (
    <div
      role={role}
      className={`flex gap-3 rounded-xl border px-4 py-3.5 text-[0.95rem] leading-relaxed ${toneClass[tone]} ${className}`}
    >
      <span className={`mt-0.5 shrink-0 ${toneIcon[tone]}`}>
        <Icon size={20} />
      </span>
      <div className="min-w-0 flex-1">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={title ? 'mt-0.5 text-ink-soft' : ''}>{children}</div>}
        {action && <div className="mt-3 flex flex-wrap gap-2">{action}</div>}
      </div>
    </div>
  )
}

export function Badge({
  children,
  tone = 'neutral',
}: {
  children: ReactNode
  tone?: 'neutral' | 'forest' | 'amber'
}) {
  const cls = {
    neutral: 'border-line bg-paper text-ink-soft',
    forest: 'border-forest-line bg-forest-soft text-forest-dark',
    amber: 'border-amber-line bg-amber-soft text-amber-ink',
  }[tone]
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${cls}`}
    >
      {children}
    </span>
  )
}

export function SectionCard({
  title,
  description,
  children,
  className = '',
  headingId,
}: {
  title: string
  description?: ReactNode
  children: ReactNode
  className?: string
  headingId?: string
}) {
  return (
    <section
      aria-labelledby={headingId}
      className={`rounded-2xl border border-line bg-card p-5 shadow-[0_1px_0_rgb(24_37_31/0.04),0_8px_24px_-16px_rgb(24_37_31/0.25)] sm:p-7 ${className}`}
    >
      <h2 id={headingId} className="font-display text-2xl font-semibold tracking-tight text-ink">
        {title}
      </h2>
      {description && <p className="mt-1.5 max-w-prose text-[0.95rem] leading-relaxed text-ink-soft">{description}</p>}
      <div className="mt-5">{children}</div>
    </section>
  )
}

export function FieldError({ id, children }: { id?: string; children: ReactNode }) {
  return (
    <p id={id} className="mt-1.5 flex items-start gap-1.5 text-sm font-medium text-brick">
      <AlertIcon size={16} className="mt-0.5 shrink-0" />
      <span>{children}</span>
    </p>
  )
}

/** Gruppo di scelte "a pulsanti" basato su veri radio button. */
export function Segmented<T extends string>({
  legend,
  name,
  value,
  options,
  onChange,
  hideLegend = false,
}: {
  legend: string
  name: string
  value: T
  options: { value: T; label: string }[]
  onChange: (v: T) => void
  hideLegend?: boolean
}) {
  return (
    <fieldset>
      <legend className={hideLegend ? 'sr-only' : 'mb-2 text-sm font-semibold text-ink'}>{legend}</legend>
      <div className="inline-flex flex-wrap gap-1 rounded-xl border border-line bg-paper p-1">
        {options.map((o) => (
          <label key={o.value} className="relative cursor-pointer">
            <input
              type="radio"
              name={name}
              value={o.value}
              checked={value === o.value}
              onChange={() => onChange(o.value)}
              className="peer sr-only"
            />
            <span className="block rounded-lg px-3.5 py-2 text-[0.95rem] font-medium text-ink-soft transition-colors hover:bg-paper-deep peer-checked:bg-forest peer-checked:text-white peer-checked:shadow-sm peer-focus-visible:outline-3 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-focus">
              {o.label}
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  )
}
