import { describeScenario, SCENARIO_LIMITS } from './scenario'

describe('scenario', () => {
  it('limits mirror the server', () => {
    expect(SCENARIO_LIMITS.factor.min).toBe(0)
    expect(SCENARIO_LIMITS.factor.minExclusive).toBe(true)
    expect(SCENARIO_LIMITS.value.min).toBe(0)
    expect(SCENARIO_LIMITS.value.minExclusive).toBe(false)
  })
  it('describes', () => {
    expect(describeScenario({ kind: 'historical' })).toMatch(/storico/)
    expect(describeScenario({ kind: 'scaled', factor: 1.2 })).toContain('+20%')
    expect(describeScenario({ kind: 'scaled', factor: 0.8 })).toContain('−20%')
    expect(describeScenario({ kind: 'flat', value: 0.12 })).toContain('0,1200 €/kWh')
  })
})
