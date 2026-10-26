# VietGeo Nova 2026

Local-first Vietnam map app. **Zero runtime dependencies** — Python 3.10+ stdlib only.
Do NOT add third-party runtime deps; `osmium` is the only optional extra (nationwide PBF import).

## Stack

- `vietgeo/` — backend: `server.py` (stdlib `http.server`, port 8765, localhost-only), `db.py` (SQLite + FTS5 + WAL), `osm.py` (Overpass client, stdlib `urllib`)
- `web/` — static HTML/CSS/JS; MapLibre GL JS 6.15.0 via unpkg CDN (no npm/bundler)
- `tools/` — `sync_admin.py` (3,321 wards), `download_osm.py` + `import_osm.py` (Geofabrik PBF, needs `osmium`), `backup.py`
- `tests/` — `unittest`, offline

## Commands

```powershell
uv sync --dev                          # create .venv + dev tools (or: py -3.11 -m venv .venv)
uv run python -m vietgeo.server        # run server -> http://127.0.0.1:8765
python -m unittest discover -s tests -v  # tests (no pytest; unittest convention)
ruff check . && ruff format --check .  # lint + format check (line-length 120, py310)
mypy vietgeo tools                     # typecheck (non-strict)
uv sync --extra osm                    # optional: pyosmium for tools/import_osm.py
```

## Conventions

- Vietnamese user-facing strings; UTF-8; ruff config in `pyproject.toml` (`select = E,F,W,I,UP,B,SIM,RUF`)
- Server refuses non-localhost binds unless `VIETGEO_CONTAINER=1` (Docker path)
- Env vars: `VIETGEO_API_TOKEN`, `VIETGEO_DB`, `VIETGEO_AUTO_ADMIN_SYNC`, `VIETGEO_CONTAINER` — see `.env.example`
- Runtime data (`data/*.sqlite3*`, `data/wards_3321.json`, `*.pbf`, `backups/`) is gitignored — never commit it
- Docker: `docker compose up --build -d` (port bound to 127.0.0.1 only)
