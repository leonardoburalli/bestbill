import { normalizeOfferUrl } from './url'

describe('normalizeOfferUrl', () => {
  it('keeps http(s)', () => {
    expect(normalizeOfferUrl('https://a.it/x')).toBe('https://a.it/x')
    expect(normalizeOfferUrl('http://a.it/')).toBe('http://a.it/')
  })
  it('prepends https:// to scheme-less', () => {
    expect(normalizeOfferUrl('www.a.it/offerta')).toBe('https://www.a.it/offerta')
    expect(normalizeOfferUrl('a.it:8080/x')).toBe('https://a.it:8080/x')
  })
  it('rejects unsafe / non-http schemes', () => {
    expect(normalizeOfferUrl('javascript:alert(1)')).toBeNull()
    expect(normalizeOfferUrl('JavaScript:alert(1)')).toBeNull()
    expect(normalizeOfferUrl('data:text/html,<b>')).toBeNull()
    expect(normalizeOfferUrl('ftp://a.it')).toBeNull()
  })
  it('null/empty/garbage', () => {
    expect(normalizeOfferUrl(null)).toBeNull()
    expect(normalizeOfferUrl('  ')).toBeNull()
    expect(normalizeOfferUrl('http://')).toBeNull()
  })
})
