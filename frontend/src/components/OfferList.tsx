import { Fragment, useState } from 'react'
import { ALL_IN_HINT, formatEur, formatEurPerKwh, formatEurPerYear } from '../lib/format'
import type { ResultItem } from '../types'
import { ChevronDownIcon } from './icons'
import { BreakEvenText, EnergyPrice, OfferBadges, OfferDetails, OfferDuration, OfferFlags, OfferLink } from './OfferParts'
import { useIsWide } from './useIsWide'

const deltaText = (n: number) => (n <= 0.005 ? 'La più economica' : `+${formatEur(n)}`)

export default function OfferList({ items, total }: { items: ResultItem[]; total?: number }) {
  const wide = useIsWide()
  // Sotto i 1280px la tabella ha meno spazio: "Rispetto alla migliore" passa sotto il costo
  // e i due prezzi al kWh si impilano in un'unica colonna.
  const roomy = useIsWide('(min-width: 1280px)')
  const [open, setOpen] = useState<Set<string>>(new Set())
  const toggle = (id: string) =>
    setOpen((s) => {
      const n = new Set(s)
      if (n.has(id)) n.delete(id)
      else n.add(id)
      return n
    })

  return wide ? (
    <OfferTable items={items} total={total} open={open} toggle={toggle} roomy={roomy} />
  ) : (
    <OfferCards items={items} total={total} open={open} toggle={toggle} />
  )
}

interface ListProps {
  items: ResultItem[]
  /** Offers matching the filters: shown as "di N" next to the rank. */
  total?: number
  open: Set<string>
  toggle: (id: string) => void
}

function OfferTable({ items, total, open, toggle, roomy }: ListProps & { roomy: boolean }) {
  const columns = roomy ? 8 : 6
  return (
    <div className="overflow-hidden rounded-2xl border border-line bg-card">
      <table className="w-full border-collapse text-left">
        <caption className="sr-only">
          Offerte ordinate per costo stimato nei prossimi 12 mesi, dalla più economica. Costo materia energia, IVA esclusa.
        </caption>
        <thead>
          <tr className="border-b border-line bg-paper text-xs uppercase tracking-wide text-ink-soft">
            <th scope="col" className="w-20 px-4 py-3 font-semibold">Pos.</th>
            <th scope="col" className="px-3 py-3 font-semibold">Offerta</th>
            <th scope="col" className="px-3 py-3 text-right font-semibold">
              Costo stimato
              <span className="block text-[0.7rem] font-normal normal-case tracking-normal">nei prossimi 12 mesi</span>
            </th>
            {roomy && <th scope="col" className="px-3 py-3 text-right font-semibold">Rispetto alla migliore</th>}
            {roomy ? (
              <>
                <th scope="col" className="px-3 py-3 text-right font-semibold">Prezzo energia</th>
                <th scope="col" className="px-3 py-3 text-right font-semibold">
                  <abbr title={ALL_IN_HINT} className="cursor-help underline decoration-dotted underline-offset-4">Costo medio tutto incluso</abbr>
                  <span className="sr-only">. {ALL_IN_HINT}</span>
                </th>
              </>
            ) : (
              <th scope="col" className="px-3 py-3 text-right font-semibold">
                Prezzi al kWh
                <span className="block text-[0.7rem] font-normal normal-case tracking-normal">
                  <abbr title={ALL_IN_HINT} className="cursor-help underline decoration-dotted underline-offset-2">cosa sono?</abbr>
                  <span className="sr-only">. {ALL_IN_HINT}</span>
                </span>
              </th>
            )}
            <th scope="col" className="px-3 py-3 text-right font-semibold">
              <abbr title="Corrispettivo commercializzazione e vendita: quota fissa annuale, già inclusa nel costo" className="no-underline">CCV</abbr> / anno
            </th>
            <th scope="col" className="px-3 py-3 text-right font-semibold"><span className="sr-only">Dettagli e link</span></th>
          </tr>
        </thead>
        <tbody>
          {items.map((it) => {
            const isOpen = open.has(it.offer_id)
            const detailId = `t-detail-${it.offer_id}`
            return (
              <Fragment key={it.offer_id}>
                <tr className={`align-top ${isOpen ? 'bg-paper/70' : 'hover:bg-paper/50'} border-b border-line/70`}>
                  <td className="px-4 py-4 font-display text-lg font-semibold tabular text-ink-soft">
                    {it.rank}
                    {total ? <span className="block font-sans text-[0.7rem] font-normal">di {total}</span> : null}
                  </td>
                  <td className="max-w-[26rem] px-3 py-4">
                    <p className="font-semibold leading-snug">{it.name}</p>
                    <p className="text-sm text-ink-soft">{it.supplier}</p>
                    <div className="mt-2"><OfferBadges item={it} /></div>
                    <OfferDuration item={it} className="mt-1.5" />
                    <BreakEvenText item={it} />
                    <OfferFlags item={it} />
                  </td>
                  <td className="px-3 py-4 text-right">
                    <span className="font-display text-xl font-semibold tabular">{formatEur(it.cost_eur)}</span>
                    <span className="block text-xs text-ink-soft">in 12 mesi</span>
                    {!roomy && (
                      <span className="mt-1.5 block text-xs tabular text-ink-soft">{deltaText(it.delta_vs_best_eur)}</span>
                    )}
                  </td>
                  {roomy && <td className="px-3 py-4 text-right text-sm tabular text-ink-soft">{deltaText(it.delta_vs_best_eur)}</td>}
                  {roomy ? (
                    <>
                      <td className="px-3 py-4 text-right text-sm tabular"><span className="whitespace-nowrap"><EnergyPrice item={it} noteClassName="mt-0.5 ml-auto block max-w-[11rem] whitespace-normal text-[0.7rem] font-normal leading-snug text-ink-soft" /></span></td>
                      <td className="whitespace-nowrap px-3 py-4 text-right text-sm font-medium tabular">{formatEurPerKwh(it.eur_per_kwh_effective)}</td>
                    </>
                  ) : (
                    <td className="whitespace-nowrap px-3 py-4 text-right text-sm tabular">
                      <span className="block text-[0.7rem] text-ink-soft">Prezzo energia</span>
                      <span className="block"><EnergyPrice item={it} noteClassName="mt-0.5 ml-auto block max-w-[11rem] whitespace-normal text-[0.7rem] font-normal leading-snug text-ink-soft" /></span>
                      <span className="mt-1.5 block text-[0.7rem] text-ink-soft">Costo medio tutto incluso</span>
                      <span className="block font-medium">{formatEurPerKwh(it.eur_per_kwh_effective)}</span>
                    </td>
                  )}
                  <td className="whitespace-nowrap px-3 py-4 text-right text-sm font-medium tabular">{formatEur(it.breakdown.fixed_fees)}</td>
                  <td className="px-3 py-4 text-right">
                    <div className="flex flex-col items-end gap-2">
                      <button
                        type="button"
                        aria-expanded={isOpen}
                        aria-controls={detailId}
                        onClick={() => toggle(it.offer_id)}
                        className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-sm font-medium text-forest hover:bg-forest-soft"
                      >
                        {isOpen ? 'Nascondi' : 'Dettagli'}
                        <ChevronDownIcon size={16} className={`transition-transform ${isOpen ? 'rotate-180' : ''}`} />
                        <span className="sr-only"> costo di {it.name}</span>
                      </button>
                      <OfferLink item={it} className="text-sm" />
                    </div>
                  </td>
                </tr>
                {isOpen && (
                  <tr className="border-b border-line/70 bg-paper/70">
                    <td />
                    <td colSpan={columns - 1} className="px-3 pb-6 pt-1">
                      <OfferDetails item={it} id={detailId} />
                    </td>
                  </tr>
                )}
              </Fragment>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function OfferCards({ items, total, open, toggle }: ListProps) {
  return (
    <ol className="space-y-3">
      {items.map((it) => {
        const isOpen = open.has(it.offer_id)
        const detailId = `c-detail-${it.offer_id}`
        return (
          <li key={it.offer_id} className="rounded-2xl border border-line bg-card p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-xs font-semibold uppercase tracking-wide text-ink-soft">
                  Posizione {it.rank}{total ? ` di ${total}` : ''}
                </p>
                <p className="mt-0.5 font-semibold leading-snug">{it.name}</p>
                <p className="text-sm text-ink-soft">{it.supplier}</p>
              </div>
              <div className="shrink-0 text-right">
                <p className="font-display text-xl font-semibold tabular">{formatEur(it.cost_eur)}</p>
                <p className="text-xs text-ink-soft">in 12 mesi</p>
              </div>
            </div>
            <div className="mt-2.5"><OfferBadges item={it} /></div>
            <OfferDuration item={it} className="mt-1.5" />
            <dl className="mt-3 grid grid-cols-2 gap-3 border-t border-dashed border-line pt-3 text-sm">
              <div>
                <dt className="text-xs text-ink-soft">Prezzo energia</dt>
                <dd className="tabular font-medium"><EnergyPrice item={it} noteClassName="mt-0.5 block text-[0.7rem] font-normal leading-snug text-ink-soft" /></dd>
              </div>
              <div>
                <dt className="text-xs text-ink-soft" title={ALL_IN_HINT}>Costo medio tutto incluso</dt>
                <dd className="tabular font-medium">{formatEurPerKwh(it.eur_per_kwh_effective)}</dd>
              </div>
              <div>
                <dt className="text-xs text-ink-soft">CCV (quota fissa di vendita)</dt>
                <dd className="tabular font-medium">{formatEurPerYear(it.breakdown.fixed_fees)}</dd>
              </div>
              <div>
                <dt className="text-xs text-ink-soft">Rispetto alla migliore</dt>
                <dd className="tabular font-medium">{deltaText(it.delta_vs_best_eur)}</dd>
              </div>
            </dl>
            <p className="mt-2 text-[0.75rem] leading-snug text-ink-soft">{ALL_IN_HINT}</p>
            <BreakEvenText item={it} />
            <OfferFlags item={it} />
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
              <button
                type="button"
                aria-expanded={isOpen}
                aria-controls={detailId}
                onClick={() => toggle(it.offer_id)}
                className="inline-flex items-center gap-1 rounded-lg px-2 py-1.5 text-sm font-medium text-forest hover:bg-forest-soft"
              >
                {isOpen ? 'Nascondi i dettagli' : 'Vedi i dettagli'}
                <ChevronDownIcon size={16} className={`transition-transform ${isOpen ? 'rotate-180' : ''}`} />
              </button>
              <OfferLink item={it} className="text-sm" />
            </div>
            {isOpen && (
              <div className="mt-3 border-t border-line pt-4">
                <OfferDetails item={it} id={detailId} />
              </div>
            )}
          </li>
        )
      })}
    </ol>
  )
}
