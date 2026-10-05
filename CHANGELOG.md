# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The version covers the whole application (API and front end), which ship
together. The ARERA catalogue is versioned separately: by its snapshot date,
with `schema_version` in `manifest.json` for its file format.

## [Unreleased]

## [1.1.0] - 2026-10-05

### Added
- "Sconti inclusi" note next to each offer's duration whenever its estimate
  includes discounts, and a "Sconti applicati" list in the offer details.
- `applied_discounts` on each `/api/compare` result.
- `discount-review.csv` written by every catalogue build (not published),
  listing how fixed-€ bonuses were interpreted.

### Fixed
- Bonuses declared as one-off but paid in monthly instalments over the
  contract (e.g. "4,17 euro/mese per 36 mesi") now count only the
  instalments of the first 12 months in the estimate. Agesp/Acinque
  "Mia Fissa 36" no longer get the full 150 € in year one.

### Changed
- The privacy note in the footer mentions Vercel Web Analytics (anonymous,
  aggregate, no cookies).

## [1.0.1] - 2026-10-02

### Fixed
- The API loads the catalogue again after the repository went public:
  without a token it downloads the release files directly instead of
  calling the GitHub API (whose 60 requests/hour unauthenticated limit is
  exhausted on Render's shared IPs), and it skips the download when the
  catalogue hasn't changed.
- Catalogues published before a field was removed from the offer model
  still load.

### Security
- Signed release-asset download URLs are no longer written to the logs.

## [1.0.0] - 2026-10-02

First public release.

### Added
- Website (React, Vite, Tailwind) in two steps: enter 12 months of
  consumption, then compare the offers available today, ranked by estimated
  spend over the next 12 months.
- Consumption entry: a 12-month period chosen with "Da"/"A" (ending at the
  last complete month), optional F1/F2/F3, pasting 12 values, a synthetic
  sample household, and import of one or more Portale Consumi CSV exports
  (one per calendar year), read in the browser and never uploaded.
- Results: best offer, ranked list (cards on mobile), chart, cost breakdown,
  CCV per year, advertised energy price after unconditional discounts next to
  the all-in average €/kWh, offer duration, break-even PUN, conditional
  discounts, one-off fees, CSV export.
- Filters for price type, source (PLACET / mercato libero) and duration
  ("12 mesi", "+ di 12 mesi"); PUN scenarios (same as the chosen period,
  scaled, flat); search by supplier or offer name; "Mostra altre 50".
- Stateless FastAPI service: `/api/compare`, `/api/offers`, `/api/comuni`,
  `/api/sample`, `/api/catalog/meta`, `/api/health`. Consumption is
  processed in memory and never stored or logged; per-IP rate limits, body
  limits and security headers.
- ARERA catalogue pipeline: PLACET and mercato libero offers, PUN, market
  parameters and supplier names from ARERA open data, normalised into a
  read-only SQLite snapshot published as a GitHub Release
  (`make catalog-publish`).
- Pricing engine for household offers: fixed and variable (PUN-indexed)
  prices, mono/F1-F23/F1-F2-F3 bands, CCV and other fixed fees, dispatching,
  power fee, one-off fees, unconditional discounts (including time-limited
  ones) and geographic restrictions. See `docs/pricing-policy.md`.
- Deployment on Vercel (front end) and Render (API) free plans;
  see `docs/deploy.md`.
- CI for the Python package and the front end.

[Unreleased]: https://github.com/leonardoburalli/bestbill/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/leonardoburalli/bestbill/compare/v1.0.1...v1.1.0
[1.0.1]: https://github.com/leonardoburalli/bestbill/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/leonardoburalli/bestbill/releases/tag/v1.0.0
