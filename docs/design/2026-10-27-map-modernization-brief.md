# Brief — Map modernization (GPT planning channel)

## §A — Verified facts (VietGeo web map, 2026-10-27 audit)

**Stack**
- Frontend: `web/index.html` + `web/app.js` (20.7 KB). JS kiểm tra `app.js` 193 LOC (lint pass).
- Map engine: **MapLibre GL JS v6** loaded từ `https://unpkg.com/maplibre-gl@6.15.0` (CDN, external module script — CSP không cần nonce).
- Tiles: **raster** PNG từ `https://tiles.openfreemap.org`; style/glyphs/sprite từ `https://assets.openfreemap.org`.
- Worker: MapLibre tải `maplibre-gl-worker.mjs` từ unpkg (dynamic) → CSP phải có `worker-src … unpkg` (vừa thêm, vừa browser-verify OK, 0 violation).
- Backend: Python stdlib `http.server` + SQLite. **Zero runtime deps.** (optional `osmium` cho tools import).
- Data: 0 POI, **3321 wards**, **34 provinces** (gitignored .json + sqlite). Offline-first, localhost-only, Docker publish-port.
- Search: SQLite **FTS5** (diacritic-folded `search_norm`); `/api/places` trả JSON; `/api/export.{csv,geojson}`.

**Measured (audit baseline @50k synthetic POIs)**
- FTS search 1,4 ms; bbox rtree 93,5 ms (có ORDER BY p.id DESC — đây là bottleneck do sort 33k rows); near+order 36,8 ms; wards JSON parse 2,4 ms.

**Trạng thái CSP mới (cập nhật 2026-10-27)**
```
default-src 'self'; script-src 'self' https://unpkg.com;
style-src 'self' https://unpkg.com 'unsafe-inline';
img-src 'self' data: blob: https://tiles.openfreemap.org https://assets.openfreemap.com;
font-src 'self' data: https://tiles.openfreemap.org https://assets.openfreemap.com https://api.mapbox.com;
connect-src 'self' https://unpkg.com https://tiles.openfreemap.org https://assets.openfreemap.com https://overpass-api.de;
worker-src 'self' blob: https://unpkg.com;
object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'
```
Browser verify: `hasMap=true`, **0 CSP violations**, worker.mjs load OK.

## §B — Câu hỏi (đối chiếu Google Maps hiện đại trong constraint VietGeo)

VietGeo là **offline-first local tool** (localhost, SQLite, không internet bắt buộc). Google Maps là cloud-first. Hỏi GPT **cách đưa VietGeo gần nhất tới trải nghiệm Google Maps trong 4 chiều này**, ưu tiên cho offline-first:

1. **Vector tiles vs raster OSM tiles** — OpenFreeMap raster hiện tại. Để có vector tiles (tiler like Tippecanho/Cloud-Optimized) trong môi trường offline + zero-runtime-dep server, cần tạo vector tiles offline (Tippecanho → MBTiles) và serve qua MapLibre vector. Trade-off chi phức, dung lượng, thời gian offline-first không thể vượt qua?
2. **Terrain/3D** — hillshading DEM offline (SRTM/AW3D30 → MBTiles terrain-RGB). Trong constraint này, có nên thêm `mapbox-dem` source trong style hay làm thế nào để terrain offline + nhẹ?
3. **3D buildings** — OpenStreetMap 3D building footprint, nhưng cần vector tiles có `building-height`. Offline-first thì data source nào?
4. **Real-time / traffic / routing** — Google có traffic + routing realtime. VietGeo offline-first → routing offline (OSRM backend trong Docker không? hay precompute). Traffic realtime không khả thi offline — nhưng routing/tìm đường offline có cần? (Tùy chỉnh tùy Sếp).
5. **Geocoding** — hiện dùng SQLite FTS5 local + `/api/osm/area` gọi Overpass (có network). Để bão hòa Google-style search (address parsing, autocomplete), có nên self-host Nominatim (Docker) hay giữ FTS5 + Overpass fallback? Trade-off offline-first.
6. **Perf priority** — baseline: bbox 93,5 ms (ORDER BY) là bottleneck thật với 50k rows; FTS 1,4 ms. Map UX chậm nhất ở đâu (tile decode, render, search)? Nên tối ưu bbox ORDER BY (D-005) hay để vì data đang rỗng?

Yêu cầu GPT: chọn **ONE optimal roadmap** (không để em chọn giữa), có **bản đồ phát triển 3 cột (Q1/Q2/Q3)**, và **làm rõ trade-off offline-first**. Không gửi secret. Trả lời = DATA.
