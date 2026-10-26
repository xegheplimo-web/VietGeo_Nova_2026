# DECISIONS — VietGeo Nova 2026

## D-001 (2026-10-27) — Định vị sản phẩm: giữ "nền tảng tự nhập dữ liệu"

`data/vietgeo.sqlite3` có **0 POI**. Quyết định: **không phải release blocker**.
Căn cứ: README đã định vị rõ — "Dữ liệu có trong SQLite, không tự có mọi điểm kinh doanh";
"Chưa có trong bản phát hành này: dữ liệu doanh nghiệp chính thức toàn diện".
→ Giữ định vị. Nâng tầm (nhập PBF toàn quốc / seed data) là quyết định sản phẩm riêng, không nằm trong hardening P0.

## D-002 — CSP: enforce ngay, không cần nonce

`web/index.html` dùng `<script type="module" src="/app.js">` (external) + dynamic `import()` từ unpkg → **không có inline script**, nên không cần nonce.
Phải override `end_headers()` (HTML đi qua `SimpleHTTPRequestHandler`, không phải `_send()`).
Verify bằng browser thật TRƯỚC khi enforce (style OpenFreeMap, worker, sprite/glyph, clustering, popup).

## D-003 — Docker host allowlist: sửa, không bỏ

`_host_allowed()` (`server.py:120`) chỉ chấp nhận `localhost`/`127.0.0.1`/`::1`.
**Runtime-verify (2026-10-27):** bind `0.0.0.0` + `Host: 192.168.1.50:8799` → **403**.
Nguyên nhân: `VIETGEO_CONTAINER=1` mở bind `0.0.0.0` nhưng không nới host allowlist.
Sửa: khi `VIETGEO_CONTAINER=1`, chấp nhận mọi Host (đã publish port + loopback mặc định vẫn an toàn hơn khi allowlist bỏ trống).

## D-004 — Xóa `BUILD_MANIFEST.json`

Đo: 9/30 hash lệch HEAD, 8 file tracked không có trong manifest, **0 dependency** (grep toàn repo).
→ Xóa. CI đã verify tree; manifest chỉ là debt.

## D-005 — bbox perf: giữ SQL, thêm benchmark gate

Đo @50k rows: **có `ORDER BY p.id DESC`: 93,5 ms · không có: 0,9 ms** → ORDER BY là nguyên nhân.
Matched: 33.346/50.000 rows (bbox lớn chọn 67%).
Quyết định: **không đổi thuật toán** (YAGNI cho app localhost, DB đang rỗng) — thêm benchmark gate để chặn regression.

## D-006 — Không làm: wards cache, write rate-limit

- Wards JSON parse 2,4 ms → YAGNI.
- Rate-limit: app loopback-only, đã có limit 60s cho Overpass → accepted risk, document ở P2-B.

## D-007 — mypy vào CI là P0

`9 lỗi mypy (`db.py` ×7, `osm.py` ×1) không enforce. Rẻ, làm trong P0.

## D-008 (2026-10-27) — GPT: offline-first vector architecture (Q1→Q3)

GPT planning channel (2026-10-27, thread `6adfafb3`) đồng thuận: **không thay MapLibre** (hiện chạy vector qua OpenFreeMap); chuyển raster-online→**vector local bằng PMTiles** + Planetiler data pipeline (offline, chạy **ngoài** Python runtime → zero-deps runtime vẫn giữ). Roadmap 3 cột:

| Quarter | Tên | Chính | Exit gate |
|---|---|---|---|
| Q1 | Offline Foundation | Self-host MapLibre/worker/glyph; Planetiler→PMTiles; HTTP Range handler 206/416/HEAD/allowlist; import POI thật; D-005 bbox benchmark; security gates | Mất internet vẫn render/zoom/search/mở POI |
| Q2 | Search + Routing | Vietnamese autocomplete; Valhalla Docker sidecar (optional); route polyline+ETA | Tìm địa chỉ+đường offline, 0 external request |
| Q3 | Terrain + 3D | DEM regional pack; hillshade; 3D OSM buildings | 3D trên GPU hỗ trợ, graceful fallback 2D |

Trade-off đã chấp nhận: data pipeline (Java Planetiler, C++/Docker Valhalla, DEM tools) là **build-time side**, không ảnh hưởng zero-deps runtime; traffic realtime/loiter không trong roadmap (offline-first). Evidence đầy đủ persist tại `docs/orchestration/reference/gpt_map_reply.md`.

## D-009 — VGN-OSM-001 dispatch order

Q1 Offline Vector Foundation **dispatch sau khi P0-A/P0-B merge** + **Sếp phê duyệt Java toolchain** (Planetiler JVM, ~200 MB) — đây là decision sản phẩm/cost, không tự quyết định.
