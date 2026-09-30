import { applyImport, parsePortaleConsumiCsv, PortaleConsumiError, readPortaleConsumiFile, suggestEndMonth } from './portaleConsumi'

const q = (cells: string[]) => cells.map((c) => `"${c} "`).join(';')
const csv = (months: string[], rows: Record<string, string[]>, eol = '\r\n') =>
  [`"";${months.map((m) => `"${m} "`).join(';')}`, ...Object.entries(rows).map(([k, v]) => q([k, ...v]))].join(eol) + eol

const zeros = (n: number) => Array(n).fill('0,00')
const HDR = ['Nov - 25', 'Dic - 25', 'Gen - 26']
const bandsCsv = () =>
  csv(HDR, {
    'Fascia unica': zeros(3),
    F1: ['10,50', '20,00', '30,25'],
    F2: ['1.000,10', '2,00', '3,00'],
    F3: ['1,00', '1,00', '1,00'],
    F4: zeros(3), F5: zeros(3), F6: zeros(3),
  })

describe('parsePortaleConsumiCsv', () => {
  it('parses header across year boundary, quoted cells with trailing spaces, thousands dots', () => {
    const r = parsePortaleConsumiCsv(bandsCsv())
    expect(r.months.map((m) => m.month)).toEqual(['2025-11', '2025-12', '2026-01'])
    expect(r.months[0]).toEqual({ month: '2025-11', kwh: 1011.6, f1: 10.5, f2: 1000.1, f3: 1 })
    expect(r.hasBands).toBe(true)
    expect(r.warnings).toEqual([])
  })
  it('handles BOM, LF and any row order', () => {
    const r = parsePortaleConsumiCsv('\uFEFF' + csv(HDR, { F3: ['1', '1', '1'], F2: ['2', '2', '2'], F1: ['3', '3', '3'] }, '\n'))
    expect(r.months[2].kwh).toBe(6)
    expect(r.hasBands).toBe(true)
  })
  it('sorts columns chronologically', () => {
    const r = parsePortaleConsumiCsv(csv(['Gen - 26', 'Dic - 25'], { 'Fascia unica': ['5', '7'] }))
    expect(r.months.map((m) => m.month)).toEqual(['2025-12', '2026-01'])
    expect(r.months[0].kwh).toBe(7)
  })
  it('Fascia unica only → mono', () => {
    const r = parsePortaleConsumiCsv(csv(HDR, { 'Fascia unica': ['100', '200', '300,5'], F1: zeros(3) }))
    expect(r.hasBands).toBe(false)
    expect(r.months[2].kwh).toBe(300.5)
    expect(r.warnings).toEqual([])
  })
  it('Fascia unica non-zero with F1..F3 → mono, with warning', () => {
    const r = parsePortaleConsumiCsv(
      csv(HDR, { 'Fascia unica': ['100', '0', '0'], F1: ['0', '1', '1'], F2: ['0', '1', '1'], F3: ['0', '1', '1'] }),
    )
    expect(r.hasBands).toBe(false)
    expect(r.warnings).toHaveLength(1)
    expect(r.months[0].kwh).toBe(100)
  })
  it('F1..F3 missing rows → mono', () => {
    const r = parsePortaleConsumiCsv(csv(HDR, { F1: ['1', '1', '1'], F2: ['1', '1', '1'] }))
    expect(r.hasBands).toBe(false)
  })
  it('non-zero F4–F6 are added to kwh, bands disabled, warning', () => {
    const r = parsePortaleConsumiCsv(
      csv(HDR, { F1: ['1', '1', '1'], F2: ['1', '1', '1'], F3: ['1', '1', '1'], F4: ['2', '0', '0'], F5: zeros(3), F6: ['0', '0', '0,5'] }),
    )
    expect(r.months.map((m) => m.kwh)).toEqual([5, 3, 3.5])
    expect(r.hasBands).toBe(false)
    expect(r.warnings.join(' ')).toMatch(/F4/)
  })
  it('>12 months supported', () => {
    const names = ['Gen', 'Feb', 'Mar', 'Apr', 'Mag', 'Giu', 'Lug', 'Ago', 'Set', 'Ott', 'Nov', 'Dic']
    const hdr = [...names.map((n) => `${n} - 24`), 'Gen - 25', 'Feb - 25']
    const r = parsePortaleConsumiCsv(csv(hdr, { 'Fascia unica': hdr.map(() => '10') }))
    expect(r.months).toHaveLength(14)
    expect(r.months[13].month).toBe('2025-02')
  })
  it.each([
    ['empty', ''],
    ['header only', '"";"Gen - 26 "\r\n'],
    ['bad header', csv(['Foo - 26'], { F1: ['1'] })],
    ['duplicate month', csv(['Gen - 26', 'Gen - 26'], { F1: ['1', '1'] })],
    ['no known rows', csv(HDR, { Altro: ['1', '1', '1'] })],
    ['bad number', csv(HDR, { F1: ['1', 'abc', '1'] })],
    ['no months', '"";\r\n"F1 ";\r\n'],
  ])('malformed: %s', (_n, text) => {
    expect(() => parsePortaleConsumiCsv(text)).toThrow(PortaleConsumiError)
  })
})

describe('readPortaleConsumiFile', () => {
  it('decodes utf-8', async () => {
    const f = new File([bandsCsv()], 'c.csv')
    expect((await readPortaleConsumiFile(f)).months).toHaveLength(3)
  })
  it('falls back to windows-1252', async () => {
    // "Consumi è" with è as single byte 0xE8 (invalid UTF-8) in a label the parser ignores
    const text = bandsCsv() + '"Note \u00e8 ";"x "\r\n'
    const bytes = Uint8Array.from(text, (c) => c.charCodeAt(0))
    expect(bytes.includes(0xe8)).toBe(true)
    const r = await readPortaleConsumiFile(new File([bytes], 'c.csv'))
    expect(r.months).toHaveLength(3)
  })
  it('rejects > 1 MB', async () => {
    const f = new File([new Uint8Array(1024 * 1024 + 1)], 'c.csv')
    await expect(readPortaleConsumiFile(f)).rejects.toBeInstanceOf(PortaleConsumiError)
  })
})

describe('suggestEndMonth', () => {
  const ms = (...m: string[]) => m.map((month) => ({ month, kwh: 1, f1: null, f2: null, f3: null }))
  it('latest imported month', () => expect(suggestEndMonth(ms('2025-11', '2026-01'), new Date(2026, 8, 30))).toBe('2026-01'))
  it('capped at last complete month', () => {
    expect(suggestEndMonth(ms('2026-07', '2026-08', '2026-09'), new Date(2026, 8, 30))).toBe('2026-08')
  })
  it('null when nothing eligible', () => {
    expect(suggestEndMonth(ms('2026-09'), new Date(2026, 8, 30))).toBeNull()
    expect(suggestEndMonth([], new Date(2026, 8, 30))).toBeNull()
  })
})

describe('applyImport', () => {
  const imported = parsePortaleConsumiCsv(bandsCsv()).months
  it('reports missing months in the window, keeps them empty', () => {
    const { rows, filled, missing } = applyImport(imported, '2026-01', true)
    expect(rows).toHaveLength(12)
    expect(rows[0].month).toBe('2025-02')
    expect(filled).toBe(3)
    expect(missing).toHaveLength(9)
    expect(missing[0]).toBe('2025-02')
    expect(rows[9]).toMatchObject({ month: '2025-11', kwh: 1011.6, f1: 10.5, f2: 1000.1, f3: 1 })
    expect(rows[0]).toEqual({ month: '2025-02', kwh: null, f1: null, f2: null, f3: null })
  })
  it('mono drops bands', () => {
    const { rows } = applyImport(imported, '2026-01', false)
    expect(rows[11]).toMatchObject({ kwh: 34.25, f1: null, f2: null, f3: null })
  })
  it('window truncates >12 months of data', () => {
    const many = Array.from({ length: 14 }, (_, i) => ({ month: `2025-${String(i + 1).padStart(2, '0')}`, kwh: 1, f1: null, f2: null, f3: null }))
      .filter((m) => Number(m.month.slice(5)) <= 12)
    const { filled, missing } = applyImport(many, '2025-12', false)
    expect(filled).toBe(12)
    expect(missing).toEqual([])
  })
})
