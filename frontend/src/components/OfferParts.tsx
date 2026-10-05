import { describeBreakEven } from '../lib/breakEven'
import { ALL_IN_HINT, discountsFlag, durationInfo, energyPriceText, energyPriceView, formatDate, formatDuration, formatEur, formatEurPerKwh, instalmentDetail, longInstalmentNote } from '../lib/format'
import { normalizeOfferUrl } from '../lib/url'
import type { Discount, OfferSource, PriceType, ResultItem } from '../types'
import { ClockIcon, ExternalIcon } from './icons'
import { Badge } from './ui'

export const SOURCE_LABEL: Record<OfferSource, string> = {
  placet: 'PLACET',
  mlibero: 'Mercato libero',
}
export const PRICE_LABEL: Record<PriceType, string> = {
  fixed: 'Prezzo fisso',
  variable: 'Prezzo variabile',
}

/** Prezzo energia: dopo gli sconti incondizionati sul prezzo dell'energia, con il listino sotto se c'è uno sconto. */
export function EnergyPrice({
  item,
  noteClassName = 'mt-0.5 block text-[0.7rem] font-normal leading-snug text-ink-soft',
}: {
  item: ResultItem
  noteClassName?: string
}) {
  const v = energyPriceView(item)
  return (
    <>
      {v.main}
      {v.note && <span className={noteClassName}>{v.note}</span>}
    </>
  )
}

export function OfferBadges({ item }: { item: ResultItem }) {
  return (
    <span className="flex flex-wrap gap-1.5">
      <Badge tone={item.price_type === 'fixed' ? 'forest' : 'amber'}>{PRICE_LABEL[item.price_type]}</Badge>
      <Badge>{SOURCE_LABEL[item.source]}</Badge>
    </span>
  )
}

/** Calm one-liner under the badges. Fixed price + months reads as a selling point (forest ink);
 *  everything else stays neutral. */
export function OfferDuration({ item, className = '' }: { item: ResultItem; className?: string }) {
  const d = durationInfo(item)
  const lock = d.kind === 'months' && item.price_type === 'fixed'
  const flag = discountsFlag(item)
  return (
    <>
      <p
        className={`flex items-center gap-1.5 text-[0.8rem] leading-snug ${lock ? 'font-medium text-forest-dark' : 'text-ink-soft'} ${className}`}
      >
        <ClockIcon size={14} className="shrink-0" />
        {formatDuration(item)}
      </p>
      {flag && (
        <div className="mt-1.5 max-w-[26rem]">
          <p className="inline-block rounded-md border border-amber-line bg-amber-soft px-2 py-0.5 text-[0.75rem] font-medium leading-snug text-amber-ink">
            {flag.text}
          </p>
          {flag.notes.map((n) => (
            <p key={n} className="mt-1 text-[0.75rem] leading-snug text-amber-ink">
              {n}
            </p>
          ))}
        </div>
      )}
    </>
  )
}

/** Segnali che cambiano la lettura del costo: una tantum, sconti condizionati, dispacciamento stimato. */
export function OfferFlags({ item }: { item: ResultItem }) {
  const flags: string[] = []
  if (item.one_off_fee_eur > 0) flags.push(`Costo una tantum ${formatEur(item.one_off_fee_eur)} già incluso`)
  if (item.conditional_discounts.length > 0)
    flags.push(
      item.conditional_discounts.length === 1
        ? '1 sconto con condizioni, non incluso'
        : `${item.conditional_discounts.length} sconti con condizioni, non inclusi`,
    )
  if (flags.length === 0) return null
  return (
    <ul className="mt-2 space-y-1 text-[0.8rem] leading-snug text-amber-ink">
      {flags.map((f) => (
        <li key={f} className="flex gap-1.5">
          <span aria-hidden="true" className="mt-[0.45em] size-1.5 shrink-0 rounded-full bg-amber-ink" />
          {f}
        </li>
      ))}
    </ul>
  )
}

export function OfferLink({ item, className = '' }: { item: ResultItem; className?: string }) {
  const href = normalizeOfferUrl(item.url)
  if (!href) return <span className="text-sm text-ink-soft">Link non disponibile</span>
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={`inline-flex items-center gap-1.5 font-medium text-forest underline decoration-forest-line decoration-2 underline-offset-4 hover:bg-forest-soft ${className}`}
    >
      Vedi l'offerta
      <ExternalIcon size={15} />
      <span className="sr-only"> di {item.supplier} (si apre in una nuova scheda)</span>
    </a>
  )
}

export function BreakEvenText({ item }: { item: ResultItem }) {
  const t = describeBreakEven(item)
  if (!t) return null
  return <p className="mt-1.5 text-[0.8rem] leading-snug text-ink-soft">{t}</p>
}

const BREAKDOWN: { key: keyof ResultItem['breakdown']; label: string; sign?: -1 }[] = [
  { key: 'energy', label: 'Energia' },
  { key: 'fixed_fees', label: 'Quota fissa di vendita (CCV)' },
  { key: 'per_kwh_extras', label: 'Altri costi al kWh' },
  { key: 'power_fee', label: 'Quota potenza' },
  { key: 'dispatching', label: 'Dispacciamento' },
  { key: 'one_off', label: 'Costi una tantum' },
  { key: 'discounts', label: 'Sconti applicati', sign: -1 },
]

function discountAmount(d: Discount): string {
  const n = d.amount.toLocaleString('it-IT', { maximumFractionDigits: 4 })
  return `${n} ${d.unit}`.trim()
}

export function AppliedDiscounts({ item }: { item: ResultItem }) {
  const applied = item.applied_discounts
  const total = Math.abs(item.breakdown.discounts)
  return (
    <div>
      <h4 className="text-sm font-semibold">Sconti applicati (già tolti dal costo)</h4>
      {applied && applied.length > 0 ? (
        <ul className="mt-1.5 space-y-2">
          {applied.map((d, i) => {
            const note = longInstalmentNote(d)
            const rate = instalmentDetail(d)
            const declaredDiffers =
              d.declared_amount_eur !== null &&
              d.declared_amount_eur !== undefined &&
              Math.abs(d.declared_amount_eur - d.amount_in_estimate_eur) > 0.005
            return (
              <li key={d.name + i} className="rounded-lg border border-amber-line bg-amber-soft px-3 py-2">
                <p className="font-medium">{d.name}</p>
                <p className="mt-0.5 text-sm text-ink">
                  Nella stima: <span className="tabular font-semibold">−{formatEur(d.amount_in_estimate_eur)}</span>
                  {declaredDiffers && (
                    <>
                      {' '}· totale dichiarato: <span className="tabular">{formatEur(d.declared_amount_eur!)}</span>
                    </>
                  )}
                </p>
                {(rate || note) && (
                  <p className="mt-0.5 text-sm text-amber-ink">
                    {[rate, note ? note.charAt(0).toUpperCase() + note.slice(1) : null].filter(Boolean).join('. ')}.
                  </p>
                )}
              </li>
            )
          })}
        </ul>
      ) : (
        <p className="mt-1 leading-relaxed text-ink-soft">
          Nella stima sono compresi sconti senza condizioni per {formatEur(total)} nei 12 mesi.
        </p>
      )}
      {applied?.some((d) => instalmentDetail(d)) && (
        <p className="mt-1.5 text-[0.8rem] text-ink-soft">
          Per i bonus pagati a rate contiamo solo le rate dei primi 12 mesi.
        </p>
      )}
    </div>
  )
}

export function OfferDetails({ item, id }: { item: ResultItem; id: string }) {
  const b = item.breakdown
  return (
    <div id={id} className="grid gap-6 lg:grid-cols-2">
      <div>
        <h4 className="text-sm font-semibold">Come si compone il costo (IVA esclusa)</h4>
        <dl className="mt-2 divide-y divide-line/70 rounded-xl border border-line bg-card text-[0.95rem]">
          {BREAKDOWN.filter((r) => b[r.key] !== 0 || r.key === 'energy').map((r) => (
            <div key={r.key} className="flex justify-between gap-4 px-3.5 py-2">
              <dt>
                {r.label}
              </dt>
              <dd className="tabular whitespace-nowrap">
                {r.sign ? '−' : ''}
                {formatEur(Math.abs(b[r.key]))}
              </dd>
            </div>
          ))}
          <div className="flex justify-between gap-4 bg-paper px-3.5 py-2.5 font-semibold">
            <dt>Totale</dt>
            <dd className="tabular whitespace-nowrap">{formatEur(b.total)}</dd>
          </div>
        </dl>
        <p className="mt-2 text-[0.8rem] text-ink-soft">
          Prezzo energia: {energyPriceText(item)}.{' '}
          Costo medio tutto incluso: {formatEurPerKwh(item.eur_per_kwh_effective)}. {ALL_IN_HINT}
        </p>
        {energyPriceView(item).note && (
          <p className="mt-1 text-[0.8rem] text-ink-soft">
            Nel prezzo energia entrano solo gli sconti senza condizioni che riducono il prezzo al kWh. Gli sconti in
            euro all'anno o una tantum non ci sono, ma sono già compresi nel costo totale.
          </p>
        )}
      </div>

      <div className="space-y-4 text-[0.95rem]">
        <div>
          <h4 className="text-sm font-semibold">Durata</h4>
          <p className="mt-1 leading-relaxed text-ink-soft">
            {formatDuration(item)}.{' '}
            {durationInfo(item).kind === 'months'
              ? item.price_type === 'fixed'
                ? 'Per questo periodo il prezzo dell\'energia non cambia.'
                : 'Il prezzo segue il mercato; questa è la durata delle condizioni indicate dal fornitore.'
              : 'Il fornitore non indica per quanto tempo valgono le condizioni: possono cambiare con un preavviso.'}
          </p>
          {discountsFlag(item) && (
            <p className="mt-2 inline-block rounded-md border border-amber-line bg-amber-soft px-2 py-0.5 text-[0.8rem] font-medium leading-snug text-amber-ink">
              {discountsFlag(item)!.text}
            </p>
          )}
        </div>

        {discountsFlag(item) && <AppliedDiscounts item={item} />}

        {describeBreakEven(item) && (
          <div>
            <h4 className="text-sm font-semibold">Se il prezzo dell'energia cambia</h4>
            <p className="mt-1 leading-relaxed text-ink-soft">{describeBreakEven(item)}.</p>
          </div>
        )}

        {item.conditional_discounts.length > 0 && (
          <div>
            <h4 className="text-sm font-semibold">Sconti con condizioni (non inclusi nel costo)</h4>
            <ul className="mt-1.5 space-y-2">
              {item.conditional_discounts.map((d, i) => (
                <li key={d.name + i} className="rounded-lg border border-amber-line bg-amber-soft px-3 py-2">
                  <p className="font-medium">
                    {d.name} <span className="tabular text-amber-ink">· {discountAmount(d)}</span>
                  </p>
                  {d.description && <p className="mt-0.5 text-sm text-ink-soft">{d.description}</p>}
                  <p className="mt-0.5 text-xs text-ink-soft">
                    {[
                      d.validity,
                      d.duration_months ? `per ${d.duration_months} mesi` : null,
                      d.consumption_from_kwh !== null || d.consumption_to_kwh !== null
                        ? `consumi ${d.consumption_from_kwh ?? 0}${d.consumption_to_kwh !== null ? `–${d.consumption_to_kwh}` : '+'} kWh/anno`
                        : null,
                    ]
                      .filter(Boolean)
                      .join(' · ')}
                  </p>
                </li>
              ))}
            </ul>
            <p className="mt-1.5 text-[0.8rem] text-ink-soft">
              Vanno richiesti o dipendono da condizioni (per esempio la domiciliazione). Se li ottieni, il costo
              scende.
            </p>
          </div>
        )}

        <p className="text-[0.8rem] leading-relaxed text-ink-soft">
          {item.valid_to ? `Valida fino al ${formatDate(item.valid_to)}. ` : ''}
          {item.supplier_vat ? `P.IVA fornitore: ${item.supplier_vat}.` : ''}
        </p>
      </div>
    </div>
  )
}
