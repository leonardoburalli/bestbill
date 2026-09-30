import { applyImport, mergePortaleFiles, suggestEndMonth, type ImportedMonth, type PortaleFile } from './portaleConsumi'

const mk = (month: string, kwh: number, bands = true): ImportedMonth =>
  bands
    ? { month, kwh, f1: kwh / 2, f2: kwh / 4, f3: kwh / 4 }
    : { month, kwh, f1: null, f2: null, f3: null }
const file = (name: string, months: ImportedMonth[], hasBands = true): PortaleFile => ({
  name,
  months,
  hasBands,
  warnings: [],
})
const range = (y: number, from: number, to: number, base = 100, bands = true) =>
  Array.from({ length: to - from + 1 }, (_, i) =>
    mk(`${y}-${String(from + i).padStart(2, '0')}`, base + from + i, bands),
  )

const f25 = () => file('2025.csv', range(2025, 1, 12))
const f26 = () => file('2026.csv', range(2026, 1, 6))
const today = new Date(2026, 6, 15) // last complete month: 2026-06

describe('mergePortaleFiles', () => {
  it('merges 2025 + 2026 into a 12-month window across the year boundary', () => {
    const r = mergePortaleFiles([f25(), f26()])
    expect(r.months).toHaveLength(18)
    expect(r.hasBands).toBe(true)
    expect(r.warnings).toEqual([])
    expect(r.files).toEqual([
      { name: '2025.csv', first: '2025-01', last: '2025-12', count: 12 },
      { name: '2026.csv', first: '2026-01', last: '2026-06', count: 6 },
    ])
    const end = suggestEndMonth(r.months, today)
    expect(end).toBe('2026-06')
    const a = applyImport(r.months, end!, r.hasBands)
    expect(a.rows[0].month).toBe('2025-07')
    expect(a.rows[11].month).toBe('2026-06')
    expect(a.filled).toBe(12)
    expect(a.missing).toEqual([])
  })

  it('is order independent', () => {
    expect(mergePortaleFiles([f26(), f25()]).months).toEqual(mergePortaleFiles([f25(), f26()]).months)
  })

  it('dedupes equal overlap silently', () => {
    const a = file('a.csv', range(2025, 1, 6))
    const b = file('b.csv', [...range(2025, 6, 6).map((m) => ({ ...m, kwh: m.kwh + 0.005 })), ...range(2025, 7, 8)])
    const r = mergePortaleFiles([a, b])
    expect(r.months.map((m) => m.month)).toEqual(range(2025, 1, 8).map((m) => m.month))
    expect(r.warnings).toEqual([])
  })

  it('keeps larger kwh on conflicting overlap and warns', () => {
    const a = file('a.csv', [mk('2025-05', 100)])
    const b = file('b.csv', [mk('2025-05', 150)])
    for (const r of [mergePortaleFiles([a, b]), mergePortaleFiles([b, a])]) {
      expect(r.months).toHaveLength(1)
      expect(r.months[0].kwh).toBe(150)
      expect(r.warnings).toHaveLength(1)
      expect(r.warnings[0]).toContain('2025-05')
      expect(r.warnings[0]).toContain('a.csv')
      expect(r.warnings[0]).toContain('b.csv')
    }
  })

  it('drops bands everywhere when some months lack them', () => {
    const r = mergePortaleFiles([file('a.csv', range(2025, 1, 3)), file('b.csv', range(2025, 4, 6, 100, false), false)])
    expect(r.hasBands).toBe(false)
    expect(r.months).toHaveLength(6)
    expect(r.months.every((m) => m.f1 === null && m.f2 === null && m.f3 === null)).toBe(true)
    expect(r.warnings).toContain('Alcuni mesi non hanno la ripartizione per fasce: userò solo i totali.')
  })

  it('ignores a duplicate upload of the same file with a warning', () => {
    const r = mergePortaleFiles([f25(), f25()])
    expect(r.months).toHaveLength(12)
    expect(r.files).toHaveLength(1)
    expect(r.warnings).toHaveLength(1)
    expect(r.warnings[0]).toContain('2025.csv')
  })

  it('prefixes per-file warnings with the file name', () => {
    const r = mergePortaleFiles([{ ...f25(), warnings: ['attenzione'] }])
    expect(r.warnings).toEqual(['2025.csv: attenzione'])
  })

  it('handles empty input', () => {
    const r = mergePortaleFiles([])
    expect(r.months).toEqual([])
    expect(r.hasBands).toBe(false)
    expect(r.files).toEqual([])
  })
})
