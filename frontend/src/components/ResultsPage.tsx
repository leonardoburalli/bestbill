/**
 * Step 2: Results page with table, chart, filters, and PUN scenario.
 */
import { useMemo, useCallback } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import type {
  CompareResponse,
  Scenario,
  PriceType,
} from '../types'

interface Props {
  response: CompareResponse
  scenario: Scenario
  setScenario: (s: Scenario) => void
  priceFilter: PriceType | null
  setPriceFilter: (f: PriceType | null) => void
  sourceFilter: 'placet' | 'mlibero' | null
  setSourceFilter: (f: 'placet' | 'mlibero' | null) => void
  onBack: () => void
}

function formatEur(n: number): string {
  return new Intl.NumberFormat('it-IT', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(n)
}

function formatKwh(n: number): string {
  return new Intl.NumberFormat('it-IT', {
    minimumFractionDigits: 4,
    maximumFractionDigits: 4,
  }).format(n)
}

export default function ResultsPage({
  response,
  scenario,
  setScenario,
  priceFilter,
  setPriceFilter,
  sourceFilter,
  setSourceFilter,
  onBack,
}: Props) {
  const { results, total_eligible, total_matching, excluded_count, excluded_by_reason } = response

  // Filtered results
  const filtered = useMemo(() => {
    return results.filter((r) => {
      if (priceFilter && r.price_type !== priceFilter) return false
      if (sourceFilter && r.source !== sourceFilter) return false
      return true
    })
  }, [results, priceFilter, sourceFilter])

  // Chart data
  const chartData = useMemo(() => {
    return filtered.slice(0, 15).map((r) => ({
      name: r.supplier.length > 15 ? r.supplier.slice(0, 15) + '…' : r.supplier,
      cost: r.cost_eur,
      offer: r.name,
      price_type: r.price_type,
    }))
  }, [filtered])

  const handleScenarioChange = useCallback(
    (kind: 'historical' | 'scaled' | 'flat') => {
      if (kind === 'historical') {
        setScenario({ kind })
      } else if (kind === 'scaled') {
        setScenario({ kind, factor: 1.0 })
      } else {
        setScenario({ kind, value: 0.12 })
      }
    },
    [setScenario],
  )

  const handleExportCSV = useCallback(() => {
    const headers = [
      'Rank', 'Fornitore', 'Offerta', 'Tipo', 'Fonte',
      'Costo (€)', 'Δ vs migliore (€)', '€/kWh eff.',
      'PUN break-even (€/kWh)', 'Link',
    ]
    const rows = filtered.map((r) => [
      String(r.rank),
      r.supplier,
      r.name,
      r.price_type,
      r.source,
      r.cost_eur.toFixed(2),
      r.delta_vs_best_eur.toFixed(2),
      r.eur_per_kwh_effective.toFixed(4),
      r.break_even_pun_eur_kwh?.toFixed(4) ?? '—',
      r.url ?? '',
    ])

    const csv = [headers.join(';'), ...rows.map((r) => r.join(';'))].join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `bestbill-confronto-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }, [filtered])

  if (results.length === 0) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <button
            onClick={onBack}
            className="text-sm text-brand hover:text-brand-dark flex items-center gap-1"
          >
            ← Indietro
          </button>
        </div>

        <div className="bg-white rounded-xl border border-border p-6 text-center">
          <p className="text-lg font-medium">Nessuna offerta trovata</p>
          <p className="text-sm text-text-muted mt-1">
            Prova a modificare i filtri o i consumi inseriti.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Top bar: back + export */}
      <div className="flex items-center justify-between">
        <button
          onClick={onBack}
          className="text-sm text-brand hover:text-brand-dark flex items-center gap-1"
        >
          ← Modifica consumi
        </button>
        <button
          onClick={handleExportCSV}
          className="text-sm text-brand hover:text-brand-dark flex items-center gap-1"
        >
          📥 Esporta CSV
        </button>
      </div>

      {/* Summary */}
      <div className="bg-white rounded-xl border border-border p-4">
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <p className="text-xs text-text-muted">Offerte eleggibili</p>
            <p className="text-xl font-bold text-brand-dark">{total_eligible.toLocaleString('it-IT')}</p>
          </div>
          <div>
            <p className="text-xs text-text-muted">Dopo i filtri</p>
            <p className="text-xl font-bold text-brand-dark">{total_matching.toLocaleString('it-IT')}</p>
          </div>
          <div>
            <p className="text-xs text-text-muted">Escluse</p>
            <p className="text-xl font-bold text-text-muted">{excluded_count.toLocaleString('it-IT')}</p>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <select
          value={priceFilter ?? ''}
          onChange={(e) => setPriceFilter((e.target.value as PriceType) || null)}
          className="px-3 py-2 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand/50"
        >
          <option value="">Tutti i tipi</option>
          <option value="fixed">Solo fisse</option>
          <option value="variable">Solo variabili</option>
        </select>
        <select
          value={sourceFilter ?? ''}
          onChange={(e) => setSourceFilter((e.target.value as 'placet' | 'mlibero') || null)}
          className="px-3 py-2 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand/50"
        >
          <option value="">Tutte le fonti</option>
          <option value="placet">Solo PLACET</option>
          <option value="mlibero">Solo Mercato Libero</option>
        </select>
      </div>

      {/* Best offer highlight */}
      {filtered[0] && (
        <div className="bg-brand-light border border-brand/30 rounded-xl p-4">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs text-brand-dark font-medium uppercase tracking-wide">
                Offerta migliore per il tuo profilo
              </p>
              <p className="text-lg font-bold text-brand-dark mt-1">
                {filtered[0].supplier} – {filtered[0].name}
              </p>
              <p className="text-2xl font-bold text-brand-dark mt-1">
                {formatEur(filtered[0].cost_eur)}
              </p>
              <p className="text-xs text-text-muted mt-1">
                {formatKwh(filtered[0].eur_per_kwh_effective)} €/kWh effettivi
              </p>
            </div>
            {filtered[0].url && (
              <a
                href={`https://${filtered[0].url}`}
                target="_blank"
                rel="noopener noreferrer"
                className="px-4 py-2 bg-brand text-white text-sm rounded-lg hover:bg-brand-dark transition-colors"
              >
                Vai all'offerta →
              </a>
            )}
          </div>
          {filtered[0].break_even_pun_eur_kwh !== null && (
            <p className="text-xs text-text-muted mt-3">
              Break-even PUN: {formatKwh(filtered[0].break_even_pun_eur_kwh)} €/kWh
              ({filtered[0].break_even_status === 'cheaper_below'
                ? 'conviene se il PUN resta sotto questo valore'
                : 'conviene sempre'})
            </p>
          )}
        </div>
      )}

      {/* Bar chart */}
      {chartData.length > 0 && (
        <div className="bg-white rounded-xl border border-border p-4">
          <h3 className="text-sm font-medium mb-3">Confronto visivo (top 15)</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 60 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis
                dataKey="name"
                angle={-45}
                textAnchor="end"
                height={80}
                tick={{ fontSize: 10 }}
                interval={0}
              />
              <YAxis
                tick={{ fontSize: 11 }}
                tickFormatter={(v: number) => `${v}€`}
              />
              <Tooltip
                formatter={(value: number) => [formatEur(value), 'Costo']}
                labelFormatter={(label: string) => label}
                contentStyle={{ fontSize: 12 }}
              />
              <Bar dataKey="cost" radius={[4, 4, 0, 0]}>
                {chartData.map((entry, i) => (
                  <Cell
                    key={`cell-${i}`}
                    fill={entry.price_type === 'fixed' ? '#0d9488' : '#f59e0b'}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div className="flex gap-4 text-xs text-text-muted mt-2">
            <span className="flex items-center gap-1">
              <span className="inline-block w-3 h-3 rounded bg-brand" /> Fissa
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block w-3 h-3 rounded bg-warm" /> Variabile
            </span>
          </div>
        </div>
      )}

      {/* Results table */}
      <div className="bg-white rounded-xl border border-border overflow-hidden">
        <div className="px-4 py-3 border-b border-border">
          <h3 className="text-sm font-medium">
            Tutte le offerte ({filtered.length})
          </h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-surface text-text-muted text-xs uppercase">
              <tr>
                <th className="px-4 py-2 text-left">#</th>
                <th className="px-4 py-2 text-left">Fornitore</th>
                <th className="px-4 py-2 text-left">Offerta</th>
                <th className="px-4 py-2 text-center">Tipo</th>
                <th className="px-4 py-2 text-right">Costo</th>
                <th className="px-4 py-2 text-right">Δ</th>
                <th className="px-4 py-2 text-right hidden sm:table-cell">€/kWh</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => (
                <tr
                  key={r.offer_id}
                  className={`border-t border-border ${
                    r.rank === 1 ? 'bg-brand-light/30' : ''
                  }`}
                >
                  <td className="px-4 py-3 font-medium">{r.rank}</td>
                  <td className="px-4 py-3">
                    <div className="font-medium">{r.supplier}</div>
                    {r.supplier_vat && (
                      <div className="text-xs text-text-muted">P.IVA {r.supplier_vat}</div>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-text-muted text-xs">{r.name}</span>
                    <div className="flex gap-1 mt-1">
                      <span className={`text-xs px-1.5 py-0.5 rounded ${
                        r.price_type === 'fixed'
                          ? 'bg-brand-light text-brand-dark'
                          : 'bg-warm-light text-warm'
                      }`}>
                        {r.price_type === 'fixed' ? 'Fissa' : 'Variabile'}
                      </span>
                      <span className="text-xs text-text-muted">
                        {r.source === 'placet' ? 'PLACET' : 'ML'}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span className={`text-xs px-2 py-1 rounded ${
                      r.price_type === 'fixed'
                        ? 'bg-brand-light text-brand-dark'
                        : 'bg-warm-light text-warm'
                    }`}>
                      {r.price_type === 'fixed' ? 'Fissa' : 'Variabile'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right font-semibold">
                    {formatEur(r.cost_eur)}
                  </td>
                  <td className={`px-4 py-3 text-right ${
                    r.delta_vs_best_eur > 0 ? 'text-text-muted' : 'text-brand-dark font-medium'
                  }`}>
                    {r.delta_vs_best_eur > 0 ? `+${formatEur(r.delta_vs_best_eur)}` : formatEur(r.delta_vs_best_eur)}
                  </td>
                  <td className="px-4 py-3 text-right text-text-muted hidden sm:table-cell">
                    {formatKwh(r.eur_per_kwh_effective)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* PUN scenario control */}
      <div className="bg-white rounded-xl border border-border p-4 space-y-3">
        <h3 className="text-sm font-medium">Scenario PUN</h3>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => handleScenarioChange('historical')}
            className={`px-3 py-2 text-sm rounded-lg border ${
              scenario.kind === 'historical'
                ? 'bg-brand text-white border-brand'
                : 'border-border hover:bg-surface'
            }`}
          >
            Storico (attuale)
          </button>
          <button
            onClick={() => handleScenarioChange('scaled')}
            className={`px-3 py-2 text-sm rounded-lg border ${
              scenario.kind === 'scaled'
                ? 'bg-brand text-white border-brand'
                : 'border-border hover:bg-surface'
            }`}
          >
            ±20% PUN storico
          </button>
          <button
            onClick={() => handleScenarioChange('flat')}
            className={`px-3 py-2 text-sm rounded-lg border ${
              scenario.kind === 'flat'
                ? 'bg-brand text-white border-brand'
                : 'border-border hover:bg-surface'
            }`}
          >
            PUN fisso: 0,12 €/kWh
          </button>
        </div>
        <p className="text-xs text-text-muted">
          Il PUN (Prezzo Unico Nazionale) varia mensilmente. Questo controllo mostra
          come cambierebbero i risultati con valori diversi del PUN.
        </p>
      </div>

      {/* Excluded offers */}
      {excluded_count > 0 && (
        <details className="bg-white rounded-xl border border-border">
          <summary className="px-4 py-3 text-sm text-text-muted cursor-pointer">
            {excluded_count.toLocaleString('it-IT')} offerte escluse (dettagli)
          </summary>
          <div className="px-4 pb-3 text-xs text-text-muted space-y-1">
            {Object.entries(excluded_by_reason).map(([reason, count]) => (
              <div key={reason}>
                {count}× — {reason}
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  )
}
