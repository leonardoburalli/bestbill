# Deploying BestBill

BestBill runs as three pieces, all on free plans:

```
browser ──► Vercel (static React app, frontend/)
              │  /api/*  rewritten server-side
              ▼
            Render (FastAPI in Docker, render.yaml)
              │  downloads at startup and every few hours
              ▼
            GitHub Release "catalog-latest" (catalog.sqlite, manifest.json, retailers.csv)
                 ▲
                 └─ make catalog-publish, run from your own machine
```

The browser only ever talks to the Vercel domain. Vercel forwards `/api/*`
to Render, so there is no CORS to configure and the strict Content Security
Policy in `frontend/vercel.json` (`connect-src 'self'`) holds.

Deploy in this order: catalogue → API → front end.

## 1. Publish the catalogue

The API serves a catalogue built from ARERA's Portale Offerte open data and
published as assets of a GitHub Release.

```bash
gh auth login          # once; needs write access to the repo
make catalog-publish   # fetch ARERA files → build → validate → upload to "catalog-latest"
```

- **Run it from a residential connection.** The Portale Offerte answers
  HTTP 403 to cloud and CI addresses (GitHub Actions included), so this is a
  manual step.
- **No TLS-inspecting VPN.** Corporate VPNs that re-sign HTTPS traffic make
  the download fail with `CERTIFICATE_VERIFY_FAILED`; disconnect first.
- Requires `uv`, `gh` and `jq`. `.cicd/publish-catalog.sh --dry-run` builds
  without uploading.
- Only `catalog.sqlite`, `manifest.json` and `retailers.csv` are uploaded;
  the raw ARERA files stay in `build/catalog/raw`.
- Running API instances pick up a new catalogue within
  `BESTBILL_REFRESH_HOURS` (default 6); no redeploy needed.

Republish whenever you want fresh offers (offers typically change every
couple of weeks).

## 2. Deploy the API to Render

The repo ships a `Dockerfile` and a `render.yaml` Blueprint: one web service,
`bestbill-api`, free plan, Frankfurt, health check `/api/health`,
auto-deploy from `main`.

1. On [dashboard.render.com](https://dashboard.render.com): **New →
   Blueprint**, connect GitHub and select the repository.
2. Render asks for the variables marked `sync: false`:
   - `BESTBILL_CORS_ORIGINS`: leave **empty** (requests arrive through Vercel).
   - `GITHUB_TOKEN`: leave empty if the repository is public: the API then
     downloads the catalogue from the public release URLs
     (`https://github.com/<repo>/releases/download/...`), which do not use the
     GitHub API quota (unauthenticated: 60 req/h per IP, exhausted on Render's
     shared IPs). For a private repository, create a fine-grained token with
     **Contents: Read-only** on this repository only. **Once the repository is
     public, remove/unset `GITHUB_TOKEN`**: a revoked or expired token makes
     GitHub answer 401 even for public data.
3. **Apply.** Then open `https://<service>.onrender.com/api/health`;
   `catalog_loaded` becomes `true` once the catalogue is downloaded.

Variables set by the Blueprint:

| Variable | Value | Why |
|---|---|---|
| `BESTBILL_REPO` | `<owner>/bestbill` | Repository holding the catalogue release. **Change it in `render.yaml` when you fork.** |
| `BESTBILL_RELEASE_TAG` | `catalog-latest` | Release tag to download |
| `BESTBILL_TRUST_PROXY` | `1` | Rate-limit by the client IP Render forwards |
| `BESTBILL_CORS_ORIGINS` | empty | Same-origin through Vercel |
| `GITHUB_TOKEN` | empty / token | Only for a private repository; unset it once public |

See the README's API section for the full list of settings.

Free-plan behaviour: the service sleeps after about 15 minutes without
traffic, and the next request takes 30–60 seconds (cold start plus the
catalogue download, since there is no persistent disk). The front end detects
this and shows a "waking up" message.

## 3. Deploy the front end to Vercel

1. On [vercel.com](https://vercel.com): **Add New → Project** and import the
   repository (grant the Vercel GitHub app access to it if it isn't listed).
2. Configure:

   | Setting | Value |
   |---|---|
   | Framework Preset | Vite |
   | Root Directory | `frontend` |
   | Install Command | `bun install --frozen-lockfile` (override) |
   | Build Command | `bun run build` (override; type-checks, then builds) |
   | Output Directory | `dist` |
   | Environment Variables | **none** |

   Do not set `VITE_API_BASE` in production: the app must call `/api` on its
   own domain.
3. **Deploy**, then check `https://<project>.vercel.app/api/health` returns the
   Render JSON.

**When you fork:** change the rewrite destination in `frontend/vercel.json`
to your own Render URL.

Every push to `main` redeploys the front end; pull requests get preview URLs.

## Releasing a new version

The application (API and front end) has one version, in `pyproject.toml`,
following [Semantic Versioning](https://semver.org/): a patch for fixes
(`1.0.1`), a minor for new features (`1.1.0`), a major for changes that
break the API contract. It is shown in `/api/health`, `/api/docs` and the
site footer. The catalogue is not versioned this way; it is identified by its
snapshot date.

While working, add each notable change to `## [Unreleased]` in
`CHANGELOG.md`. To release:

1. On a branch, bump `version` in `pyproject.toml` **and**
   `frontend/package.json` (a test fails if they differ), run `uv lock` and
   `make openapi`.
2. In `CHANGELOG.md`, rename `## [Unreleased]` to `## [x.y.z] - YYYY-MM-DD`,
   add a fresh empty `## [Unreleased]` above it, and update the links at the
   bottom.
3. Open a pull request, let CI pass, merge. Render and Vercel deploy `main`.
4. Tag the merge commit and publish the release from the changelog entry:

   ```bash
   git checkout main && git pull
   git tag -a vX.Y.Z -m "vX.Y.Z" && git push origin vX.Y.Z
   gh release create vX.Y.Z --title "vX.Y.Z" --notes "<the changelog entry>"
   ```

5. Check `/api/health` on the live site reports the new `version`.

## Local development

```bash
# API on a downloaded catalogue
gh release download catalog-latest -D catalog-latest --clobber
make api-local        # http://localhost:8000/api/docs

# front end against that local API (second terminal)
make frontend-dev     # http://localhost:5173
```

`cd frontend && bun run dev` alone proxies `/api` to the live Render service
instead.

## Checks before going live

- `make check` (Python tests + lint) and `make frontend` (type-check, tests,
  build) pass; CI runs both on every pull request.
- `/api/health` shows `catalog_loaded: true` and a recent `snapshot_date`.
- A comparison with "Prova con un esempio" works on the Vercel URL.
