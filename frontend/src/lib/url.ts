/** Return a safe http(s) URL for an offer link, or null. */
export function normalizeOfferUrl(u: string | null): string | null {
  if (!u) return null
  const t = u.trim()
  if (!t) return null
  // "scheme:" prefix (but not "host:port")
  const hasScheme = /^[a-z][a-z0-9+.-]*:(?!\d+(\/|$))/i.test(t)
  const candidate = hasScheme ? t : `https://${t.replace(/^\/\//, '')}`
  try {
    const url = new URL(candidate)
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return null
    if (!url.hostname) return null
    return url.href
  } catch {
    return null
  }
}
