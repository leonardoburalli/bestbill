import { buildMonths, defaultStartMonth, formatMonthLong, formatMonthShort, monthOptions,
  lastCompleteMonth, startFromEnd, endFromStart, endMonthOptions, startMonthOptions } from './months'

describe('months', () => {
  it('defaultStartMonth: 12 months ending last complete month', () => {
    expect(defaultStartMonth(new Date(2026, 8, 30))).toBe('2025-09') // Sep 2025..Aug 2026
    expect(defaultStartMonth(new Date(2026, 0, 15))).toBe('2025-01') // Jan..Dec 2025
  })
  it('buildMonths crosses year boundary', () => {
    const m = buildMonths('2024-09')
    expect(m).toHaveLength(12)
    expect(m[0]).toBe('2024-09')
    expect(m[4]).toBe('2025-01')
    expect(m[11]).toBe('2025-08')
  })
  it('formats', () => {
    expect(formatMonthShort('2024-09')).toBe('set 24')
    expect(formatMonthLong('2024-09')).toBe('settembre 2024')
    expect(formatMonthLong('2025-01')).toBe('gennaio 2025')
  })
  it('monthOptions newest first, starting at default', () => {
    const today = new Date(2026, 8, 30)
    const o = monthOptions(today, 3)
    expect(o).toHaveLength(36)
    expect(o[0]).toBe(defaultStartMonth(today))
    expect(o[1]).toBe('2025-08')
    expect(o[12]).toBe('2024-09')
  })
  it('lastCompleteMonth / startFromEnd / endFromStart', () => {
    expect(lastCompleteMonth(new Date(2026, 0, 5))).toBe('2025-12')
    expect(lastCompleteMonth(new Date(2026, 8, 30))).toBe('2026-08')
    expect(startFromEnd('2026-08')).toBe('2025-09')
    expect(startFromEnd('2026-01')).toBe('2025-02')
    expect(endFromStart('2025-09')).toBe('2026-08')
    expect(endFromStart(startFromEnd('2026-03'))).toBe('2026-03')
  })
  it('endMonthOptions / startMonthOptions', () => {
    const today = new Date(2026, 8, 30)
    const e = endMonthOptions(today)
    expect(e).toHaveLength(36)
    expect(e[0]).toBe('2026-08')
    expect(e[1]).toBe('2026-07')
    expect(startMonthOptions(today)).toEqual(e.map(startFromEnd))
    expect(endMonthOptions(today, 1)).toHaveLength(12)
  })
})
