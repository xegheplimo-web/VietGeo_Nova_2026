# Verification report — VietGeo Nova 1.0.0 (2026-10-27)

## Completed locally

- All **14 unittest** cases pass (SQLite FTS accent folding, RTree, near ordering, data validation, OSM source protection, CSV formula escaping, province count, REST HTTP CRUD, atomic import rollback, Origin rejection, simulated Overpass acquisition).
- `python -m compileall` passes for backend, tools and tests.
- `node --check web/app.js` passes.
- Static HTML inspected for duplicate element IDs: **42 total / 42 unique**.
- `GET /api/health` returned HTTP 200 with API version on a localhost smoke server.

## Not verifiable in this build environment

- MapLibre/CDN and OpenFreeMap vector tiles loaded from the public Internet (container browser network is restricted).
- Live Overpass response (mocked in tests; real availability/network limits external).
- Live Geofabrik PBF download and pyosmium import (no public network in build container).
- The actual `all-ward.json` download at user runtime; source was independently inspected and expected 3,321 records.
- Windows .bat and Docker startup on actual user machine.

No production SLA or "complete / newest POI" claim is made without a dated, independently verified data snapshot.
