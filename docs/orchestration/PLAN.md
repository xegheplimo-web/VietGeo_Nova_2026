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
