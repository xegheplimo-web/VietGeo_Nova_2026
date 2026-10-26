# Audit brief — VietGeo Nova 2026 (sent to GPT 2026-10-27)

## §A — Verified local-recon facts (measured, not assumed)

**Repo / runtime**
- Path `F:\VietGeo_Nova_2026`; public GitHub `xegheplimo-web/VietGeo_Nova_2026`; branch `main`; HEAD `c8a60f9`.
- CI run `40388531385` (CI) + `40388531376` (CodeQL) + `40388538948` (Dependency Graph): **11/11 jobs success**.
- Stack: Python stdlib only (`http.server`, `sqlite3`, `urllib`), zero runtime deps; `osmium` optional. Python 3.10+ (Dockerfile 3.13-slim).
- LOC: `vietgeo/server.py` 453 · `vietgeo/db.py` 304 · `vietgeo/osm.py` 175 · `tools/*` 29–104 · `web/app.js` 193 · `tests/test_vietgeo.py` 248.

**Data (measured)**
- `data/provinces_34.json` tracked: 34 provinces, Σ wards = 3321.
- `data/wards_3321.json` gitignored, 284 KB, 3321 unique codes; `data/vietgeo.sqlite3` integrity `ok` but **0 POI rows** (empty app).
- `uv.lock` — `uv lock --check` exit 0 (valid). Secrets scan: 0 matches (working tree + full git log).

**Quality gates (measured locally)**
- `unittest`: 14/14 pass. `ruff check .` + `ruff format --check .`: clean (ruff 0.17.2).
- Coverage (branch): **TOTAL 64%** — `db.py` 76% · `osm.py` 49% · `server.py` 50%.
- `mypy vietgeo tools`: **8 errors** (`db.py` arg-type ×3, `osm.py` return-value, …) — mypy is NOT in CI.
- Perf @50k synthetic rows: FTS search 1.4 ms · **bbox rtree 90.8 ms** · near+order 36.8 ms · category 1.0 ms · wards JSON parse 2.4 ms.

**Security posture**
- Present: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Cache-Control: no-store` on `/api/*`; Host allowlist (`localhost`/`127.0.0.1`/`::1`; `0.0.0.0` only when `VIETGEO_CONTAINER=1`); Origin check on writes; optional `VIETGEO_API_TOKEN` Bearer; parameterized SQL; FTS5 token escaping; CSV formula-injection defense.
- **Missing: no `Content-Security-Policy`** (page loads MapLibre from unpkg CDN + inline module script). No rate limit on write endpoints.

**Hygiene**
- `BUILD_MANIFEST.json` is **stale**: 9/30 recorded hashes no longer match HEAD, and 8 tracked files (`.devin/*`, `.env.example`, `.pre-commit-config.yaml`, `.python-version`, `AGENTS.md`, `BUILD_MANIFEST.json` itself, `uv.lock`) are absent from it.
- `Dockerfile` copies only `data/provinces_34.json` → image has no wards data (compose mounts `./data`).
- Frontend renders all user strings via `textContent` (no innerHTML sinks found).

## §B — Execution options and trade-offs

| # | Issue | Option A | Option B | Option C |
|---|---|---|---|---|
| 1 | No CSP | Strict CSP with per-request nonce for the inline module + CDN allowlist | CSP `report-only` only | Leave as-is |
| 2 | bbox query 90 ms @50k | Keep `ORDER BY id DESC`, add composite index + push LIMIT down | Window function (`ROW_NUMBER`) | Drop sort for bbox path (rtree order) |
| 3 | Stale manifest | Regenerate + add CI step asserting manifest == tracked tree | Delete `BUILD_MANIFEST.json` | Keep stale (no action) |
| 4 | Coverage 64% | Raise to ≥85% + coverage gate in CI | Add tests only for P0 paths | Keep as-is |
| 5 | No write rate-limit | In-memory token bucket per client IP | None (localhost single-user app) | None, document as accepted risk |

## Cross-questions for GPT

1. **CSP**: with an inline `<script type="module" src="/app.js">` plus unpkg MapLibre + OpenFreeMap tiles, what is the minimal correct CSP that does not break the map? Nonce vs hash — which is safer/cheaper here, and what exactly must be allowed (script-src/style-src/img-src/connect-src)?
2. **bbox performance**: 90 ms at 50k rows is fine for a local-first single-user tool, but is the 90 ms from the `ORDER BY` full sort or from the rtree join? Should we optimize now (Option A) or is this premature (YAGNI) given the empty-DB state?
3. **Manifest**: does a SHA-256 manifest add real value for a public repo whose CI already verifies the tree, or is it pure maintenance debt that should be deleted?
4. **Priority order**: given P0-1 manifest, P0-2 CSP, P0-3 wards JSON re-parse, P0-4 bbox perf — which should ship first, and which of these (if any) is genuinely blocking a "complete, stable, secure" v1.0.0 claim?
