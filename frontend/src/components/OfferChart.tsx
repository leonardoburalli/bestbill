import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { formatEur, formatEurCompact } from '../lib/format'
import type { ResultItem } from '../types'

const short = (s: string, n: number) => (s.length > n ? s.slice(0, n - 1).trimEnd() + '…' : s)

/** Grafico a barre delle prime offerte (caricato solo quando serve). */
export default function OfferChart({ items }: { items: ResultItem[] }) {
  const data = items.slice(0, 10).map((r, i) => ({
    id: r.offer_id,
    pos: `${r.rank}. ${short(r.supplier, 22)}`,
    full: `${r.rank}. ${r.supplier} — ${r.name}`,
    cost: r.cost_eur,
    best: i === 0,
  }))
  const byId = new Map(data.map((d) => [d.id, d]))
  const summary = `Grafico a barre: costo stimato delle prime ${data.length} offerte, da ${formatEur(data[0].cost)} a ${formatEur(data[data.length - 1].cost)}. I dati sono nella tabella qui sotto.`

  return (
    <div role="img" aria-label={summary} style={{ height: data.length * 40 + 36 }} className="w-full text-ink">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 64, bottom: 4, left: 0 }} barCategoryGap={6}>
          <CartesianGrid horizontal={false} stroke="#ddd5c3" />
          <XAxis type="number" domain={[0, 'dataMax']} tickFormatter={(v: number) => formatEurCompact(v)} tick={{ fill: '#4a5852', fontSize: 12 }} stroke="#b9af98" />
          <YAxis
            type="category"
            dataKey="id"
            width={window.innerWidth < 640 ? 104 : 190}
            tickFormatter={(id: string) => byId.get(id)?.pos ?? ''}
            tick={{ fill: '#18251f', fontSize: 12 }}
            stroke="#b9af98"
          />
          <Tooltip
            cursor={{ fill: 'rgb(29 90 68 / 0.07)' }}
            labelFormatter={(id) => byId.get(String(id))?.full ?? ''}
            formatter={(v) => [formatEur(Number(v)), 'Costo stimato (IVA esclusa)']}
            contentStyle={{ borderRadius: 10, border: '1px solid #ddd5c3', fontSize: 13 }}
          />
          <Bar dataKey="cost" radius={[0, 6, 6, 0]} isAnimationActive={false}>
            {data.map((d) => (
              <Cell key={d.id} fill={d.best ? '#1d5a44' : '#a9cbb8'} />
            ))}
            <LabelList dataKey="cost" position="right" formatter={(v: unknown) => formatEurCompact(Number(v))} style={{ fill: '#18251f', fontSize: 12, fontWeight: 600 }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
