# VietGeo Nova 2026 — Plan (P0 / P1 / P2)

Nguồn: audit 2026-10-27 (`docs/design/2026-10-27-audit-brief.md` + `-reply.md`).
Baseline: commit `c8a60f9`, CI run `40388531385` xanh, tests 14/14, ruff sạch.

## P0 — hardening (release blocker)

| Card | Scope (write) | Nội dung |
|---|---|---|
| P0-A | `vietgeo/server.py`, `tests/test_vietgeo.py` | (1) Thêm `Content-Security-Policy` qua override `end_headers()`; (2) Sửa host-allowlist khi bind `0.0.0.0` trong container |
| P0-B | `vietgeo/db.py`, `vietgeo/osm.py`, `.github/workflows/ci.yml`, `pyproject.toml`, `BUILD_MANIFEST.json` | (1) Sửa 9 lỗi mypy + thêm job mypy vào CI; (2) Xóa `BUILD_MANIFEST.json` đã stale |

## P1 — chất lượng / bảo trì (chạy sau khi P0 merge)

| Card | Scope | Nội dung |
|---|---|---|
| P1-A | `tests/` (+ `pyproject.toml`, `ci.yml`) | Coverage 64% → ≥80%: thêm test cho 6 endpoint chưa test + `osm.import_small_area` real path |
| P1-B | `scripts/bench_bbox.py`, `ci.yml` | Benchmark gate cho query bbox: freeze baseline @50k, assert p95 < ngưỡng |

## P2 — cải thiện (không blocker, tuỳ chọn)

| Card | Nội dung |
|---|---|
| P2-A | Self-host MapLibre thay CDN unpkg (tăng tính tái lập) |
| P2-B | Document accepted risk: không rate-limit write API (app loopback-only, đã có limit 60s cho Overpass) |

## Thứ tự & phụ thuộc

```
P0-A ─┐
      ├──(merge)──► P1-A
P0-B ─┘
P1-B độc lập, chạy sau P0
```

## Ngân sách

- Wave 1: P0-A + P0-B song song (2 worktree, write scope không chồng), mỗi lane ≤ 1500s.
- Wave 2: P1-A, P1-B.
- Điều kiện dừng: ≥2 fail cùng nguyên nhân gốc → dừng dispatch, vào maintenance lane.

## Q1–Q3 roadmap (D-008 — xem DECISIONS.md D-008 chi tiết)

Offline-first vector architecture (GPT 2026-10-27, không thay MapLibre). Runtime Python stdlib zero-deps vẫn được bảo toàn; pipeline build (Planetiler/Valhalla/Dem) là side.

| Quarter | Tên | Mục tiêu | Exit gate | Chặn P0? |
|---|---|---|---|---|
| Q1 | Offline Foundation | Self-host MapLibre/worker; Planetiler→PMTiles; HTTP Range handler; import POI thật; D-005 benchmark | Mất internet vẫn render/zoom/search/POI | Không |
| Q2 | Search + Routing | Vietnamese autocomplete; Valhalla sidecar; route polyline+ETA | Tìm đường offline, 0 external request | Không |
| Q3 | Terrain + 3D | DEM regional; hillshade; 3D OSM buildings | Graceful fallback 2D | Không |

## VGN-OSM-001 — Offline Vector Foundation (Q1, chặn sau P0)

**Scope:** implement HTTP Range handler trong Python stdlib (206/416/HEAD/byte-range/allowlist), serve 1 sample PMTiles archive (tải từ Protomaps samples — không cần Planetiler ngay), MapLibre render local.
**Write scope:** `vietgeo/server.py` (+ `docs/` mô tả offline pack).
**Pre-req sản phẩm:** **Sếp phê duyệt Java toolchain** (Planetiler JVM, ~200 MB) cho bước build PMTiles Việt Nam thật — dispatch task này sau khi P0-A/P0-B merge + Sếp OK toolchain.
**Acceptance:** `curl -H "Range: bytes=0-262" <archive>` → `206 Partial Content` + `Content-Range`; HEAD → 200 + `Accept-Ranges: bytes`; offline mode (block internet) → 0 external request; regression POI/CRUD/FTS test PASS.
