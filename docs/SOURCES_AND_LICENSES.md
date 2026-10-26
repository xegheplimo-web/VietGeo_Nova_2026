# Sources, data provenance, and licenses — VietGeo Nova 2026

## Dataset 1 — Vietnam post-2025 administrative divisions
- Author/maintainer: **Open Admin Data** (`open-admin-data/vietnam-administrative-divisions`).
- Source: https://github.com/open-admin-data/vietnam-administrative-divisions
- Raw endpoint: https://raw.githubusercontent.com/open-admin-data/vietnam-administrative-divisions/main/data/all-ward.json
- Province source: `data/all-province.json` from same project.
- License: **Creative Commons Attribution 4.0 International (CC BY 4.0)**.
- Project's reported update: **2026-09-08** (not necessarily the current revision date at runtime).
- Packaged data: 34 province/city names, codes, representative coordinates and expected ward counts in `data/provinces_34.json`.
- On-first-start opt-in by default: downloads the 3,321 wards; `tools/sync_admin.py` validates expected 3,321 unique codes, atomic-writes, records SHA256 and retrieval metadata.
- Important caveat: **Representative coordinates** are not official legal boundary polygons. Legal acts and effective-date verification remain separate.

## Dataset 2 — OpenStreetMap and Geofabrik
- Original contributions: © OpenStreetMap contributors; data license **ODbL 1.0**.
- Attribution URL: https://www.openstreetmap.org/copyright
- Vietnam PBF extract: https://download.geofabrik.de/asia/vietnam.html
- User-download URL: https://download.geofabrik.de/asia/vietnam-latest.osm.pbf
- Live small-area query: https://overpass-api.de/ (user-initiated only, with limits).
- OSM content **not bundled**; the application has a source-aware import process. OSM dataset licensing is not relicensed MIT just because application code uses MIT.
- No guarantee of completeness, business verification, legal address normalization, or realtime updates for any OSM POI.

## Basemap and UI runtime
- MapLibre GL JS project: https://maplibre.org/maplibre-gl-js/ (BSD-3-Clause), pinned to 6.15.0 via UNPKG CDN, https://unpkg.com/.
- OpenFreeMap: https://openfreemap.org/ / `https://tiles.openfreemap.org/styles/liberty` (online style/vector tiles). Continue to show provider and OpenStreetMap contributor attribution.
- Browser fetches external JS/CSS and map tiles. This is **not a full offline map**. Public endpoints can change or be rate limited; evaluate policy and production hosting before public rollout.

## Application code
- Files written for VietGeo Nova in this distribution: MIT, `LICENSE`.
- MIT applies only to new application code/docs. Distinct data and dependency licenses take precedence for their own material.
- No Google Maps bulk extraction, Google imagery, or proprietary business registries are bundled or authorized by this project.
