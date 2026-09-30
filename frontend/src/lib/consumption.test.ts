import {
  emptyRows, parseItalianNumber, parsePastedValues, reanchorRows, rowsFromApi,
  toRequestMonths, validateRows, BAND_TOLERANCE_MESSAGE, type MonthRow,
} from './consumption'

const filled = (kwh = 100): MonthRow[] => emptyRows('2025-01').map((r) => ({ ...r, kwh }))

describe('parseItalianNumber', () => {
  it.each([
    ['1.234,5', 1234.5], ['180', 180], ['', null], ['  ', null], ['abc', null],
    ['1,5', 1.5], ['1.234', 1234], ['1.5', 1.5], ['0', 0], ['12,3,4', null], ['1.234.567,89', 1234567.89],
  ])('%s → %s', (input, out) => expect(parseItalianNumber(input)).toBe(out))
})

describe('parsePastedValues', () => {
  it('splits on newline, tab, semicolon and spaces', () => {
    expect(parsePastedValues('100\n200,5\t300;1.000  400')).toEqual([100, 200.5, 300, 1000, 400])
  })
  it('drops garbage', () => expect(parsePastedValues('a 1 b')).toEqual([1]))
})

describe('rows', () => {
  it('emptyRows / reanchorRows keep values by position', () => {
    const rows = filled(50)
    rows[0].kwh = 7
    const re = reanchorRows(rows, '2024-06')
    expect(re[0]).toMatchObject({ month: '2024-06', kwh: 7 })
    expect(re[11].month).toBe('2025-05')
  })
  it('rowsFromApi detects bands', () => {
    const r = rowsFromApi([{ month: '2025-02', kwh: 10, f1: 5, f2: 3, f3: 2 }, { month: '2025-01', kwh: 10, f1: 5, f2: 3, f3: 2 }])
    expect(r.start).toBe('2025-01')
    expect(r.hasBands).toBe(true)
    expect(rowsFromApi([{ month: '2025-01', kwh: 1 }]).hasBands).toBe(false)
  })
})

describe('validateRows', () => {
  it('requires all kwh, allows 0', () => {
    const rows = filled(0)
    expect(validateRows(rows, false)).toMatchObject({ ok: true, totalKwh: 0 })
    rows[3].kwh = null
    const v = validateRows(rows, false)
    expect(v.ok).toBe(false)
    expect(v.issues[0]).toMatchObject({ index: 3, field: 'kwh' })
  })
  it('bounds', () => {
    const rows = filled(100)
    rows[0].kwh = 100_001
    rows[1].kwh = -1
    expect(validateRows(rows, false).issues.map((i) => i.index)).toEqual([0, 1])
    rows[0].kwh = 100_000
    expect(validateRows(rows, false).issues.map((i) => i.index)).toEqual([1])
  })
  it('bands: all three required, tolerance 0.5%', () => {
    const rows: MonthRow[] = filled(1000).map((r) => ({ ...r, f1: 400, f2: 300, f3: 300 }))
    expect(validateRows(rows, true).ok).toBe(true)
    rows[0].f3 = 305 // exactly +0.5% → ok
    expect(validateRows(rows, true).ok).toBe(true)
    rows[0].f3 = 306
    expect(validateRows(rows, true).issues[0]).toMatchObject({ index: 0, field: 'bands', message: BAND_TOLERANCE_MESSAGE })
    rows[0].f3 = 300
    rows[1].f2 = null
    expect(validateRows(rows, true).issues[0]).toMatchObject({ index: 1, field: 'bands' })
    expect(validateRows(rows, false).ok).toBe(true) // bands ignored when off
  })
  it('zero kwh with bands requires zero bands', () => {
    const rows = filled(0).map((r) => ({ ...r, f1: 0, f2: 0, f3: 0 }))
    expect(validateRows(rows, true).ok).toBe(true)
    rows[0].f1 = 1
    expect(validateRows(rows, true).ok).toBe(false)
  })
})

describe('toRequestMonths', () => {
  it('omits bands when off, all-or-none when on', () => {
    const rows = filled(100).map((r) => ({ ...r, f1: 50, f2: 25, f3: 25 }))
    expect(toRequestMonths(rows, false)[0]).toEqual({ month: '2025-01', kwh: 100 })
    expect(toRequestMonths(rows, true)[0]).toEqual({ month: '2025-01', kwh: 100, f1: 50, f2: 25, f3: 25 })
  })
})
