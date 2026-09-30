import { ALL_IN_HINT, formatEnergyPrice, formatEur, formatEurPerKwh, formatEurPerMonth, formatEurPerYear } from '../lib/format'
import type { ResultItem } from '../types'
import { TrophyIcon } from './icons'
import { BreakEvenText, OfferBadges, OfferDuration, OfferFlags, OfferLink } from './OfferParts'

export default function BestOffer({ item, next }: { item: ResultItem; next?: ResultItem }) {
  const overall = item.rank === 1
  return (
    <section
      aria-labelledby="h-best"
      className="relative overflow-hidden rounded-2xl border-2 border-forest bg-forest-soft p-5 shadow-[0_18px_40px_-24px_rgb(29_90_68/0.6)] sm:p-7"
    >
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-16 -top-16 size-56 rounded-full bg-forest/10"
      />
      <p className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-forest-dark">
        <TrophyIcon size={18} />
        <span id="h-best">
          {overall ? 'L\'offerta che ti costerebbe meno nei prossimi 12 mesi' : `La migliore con questi filtri (in assoluto è la n. ${item.rank})`}
        </span>
      </p>

      <div className="relative mt-4 grid gap-5 md:grid-cols-[1fr_auto] md:items-end">
        <div className="min-w-0">
          <p className="font-display text-2xl font-semibold leading-tight sm:text-3xl">{item.name}</p>
          <p className="mt-1 text-lg text-ink-soft">{item.supplier}</p>
          <div className="mt-3"><OfferBadges item={item} /></div>
          <OfferDuration item={item} className="mt-2 text-sm" />
          <BreakEvenText item={item} />
          <OfferFlags item={item} />
          <div className="mt-4"><OfferLink item={item} className="text-base" /></div>
        </div>

        <div className="md:text-right">
          <p className="font-display text-4xl font-semibold tabular sm:text-5xl">{formatEur(item.cost_eur)}</p>
          <p className="mt-1 text-sm text-ink-soft">
            stima per i prossimi 12 mesi · materia energia, IVA esclusa
          </p>
          <dl className="mt-3 grid grid-cols-2 gap-x-5 gap-y-1 text-left md:ml-auto md:max-w-[19rem]">
            <div>
              <dt className="text-xs text-ink-soft">Prezzo energia</dt>
              <dd className="text-sm font-semibold tabular">{formatEnergyPrice(item.energy_price_eur_kwh, item.energy_price_kind)}</dd>
            </div>
            <div>
              <dt className="text-xs text-ink-soft">Costo medio tutto incluso</dt>
              <dd className="text-sm font-semibold tabular">{formatEurPerKwh(item.eur_per_kwh_effective)}</dd>
            </div>
          </dl>
          <p className="mt-1 text-[0.8rem] leading-snug text-ink-soft md:ml-auto md:max-w-[19rem]">{ALL_IN_HINT}</p>
          <div className="mt-3 rounded-xl border border-forest/30 bg-card/70 px-3.5 py-2.5 text-left md:ml-auto md:max-w-[19rem]">
            <p className="text-sm font-semibold text-forest-dark">Quota fissa di vendita (CCV)</p>
            <p className="mt-0.5 flex flex-wrap items-baseline gap-x-2 tabular">
              <span className="font-display text-2xl font-semibold">{formatEurPerYear(item.breakdown.fixed_fees)}</span>
              <span className="text-sm text-ink-soft">≈ {formatEurPerMonth(item.breakdown.fixed_fees / 12)}</span>
            </p>
            <p className="mt-1 text-[0.8rem] leading-snug text-ink-soft">
              Si paga ogni mese, anche se non consumi. È già compresa nel totale.
            </p>
          </div>
          {next && (
            <p className="mt-2 text-sm text-ink-soft">
              La successiva costerebbe{' '}
              <strong className="tabular text-ink">{formatEur(Math.max(0, next.cost_eur - item.cost_eur))}</strong>{' '}
              in più.
            </p>
          )}
        </div>
      </div>
    </section>
  )
}
