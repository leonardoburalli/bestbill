export default function ExcludedOffers({
  count,
  byReason,
}: {
  count: number
  byReason: Record<string, number>
}) {
  if (count <= 0) return null
  const entries = Object.entries(byReason).sort((a, b) => b[1] - a[1])
  return (
    <details className="rounded-2xl border border-line bg-card px-5 py-4">
      <summary className="cursor-pointer select-none rounded-md text-[0.95rem] font-medium">
        {count.toLocaleString('it-IT')} {count === 1 ? 'offerta esclusa' : 'offerte escluse'} dal confronto
      </summary>
      <div className="mt-3 text-sm leading-relaxed text-ink-soft">
        <p>
          Non le abbiamo confrontate perché non possiamo calcolarne il costo in modo affidabile con le regole
          che usiamo, oppure non sono più sottoscrivibili. Motivi:
        </p>
        <ul className="mt-2 divide-y divide-line/70 rounded-lg border border-line">
          {entries.map(([reason, n]) => (
            <li key={reason} className="flex justify-between gap-4 px-3 py-2">
              <span>{reason}</span>
              <span className="tabular font-medium text-ink">{n.toLocaleString('it-IT')}</span>
            </li>
          ))}
        </ul>
      </div>
    </details>
  )
}
