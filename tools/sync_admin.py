"""Refresh post-2025 Vietnam administrative centroids (NOT legal boundary polygons).
CC-BY-4.0: https://github.com/open-admin-data/vietnam-administrative-divisions
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
URL = "https://raw.githubusercontent.com/open-admin-data/vietnam-administrative-divisions/main/data/all-ward.json"
TARGET = ROOT / "data" / "wards_3321.json"


def transform(records):
    if not isinstance(records, list) or len(records) != 3321:
        raise ValueError(
            f"Nguồn có {len(records) if isinstance(records, list) else '?'} đơn vị, dự kiến 3321. Không ghi đè."
        )
    output = []
    seen = set()
    for r in records:
        code = str(r["id"])
        parent = str(r["parent"]["id"])
        name = str(r["name"]["local"])
        if code in seen or not code or not parent or not name:
            raise ValueError("Mã hành chính trùng/thiếu")
        seen.add(code)
        pos = r.get("geo") or {}
        lat = float(pos["lat"])
        lon = float(pos["lon"])
        if not (7.5 <= lat <= 24.5 and 100 <= lon <= 112):
            raise ValueError(f"Tọa độ sai {code}")
        output.append(
            {
                "code": code,
                "name": name,
                "province_code": parent,
                "lat": lat,
                "lon": lon,
            }
        )
    return output


def main():
    p = argparse.ArgumentParser(description="Đồng bộ 3.321 xã/phường tại nguồn mở (tọa độ đại diện)")
    p.add_argument("--force", action="store_true", help="Tải lại khi đã có dữ liệu")
    args = p.parse_args()
    if TARGET.exists() and not args.force:
        print("Đã có", TARGET, "(dùng --force nếu muốn làm mới)")
        return
    req = Request(URL, headers={"User-Agent": "VietGeoNova/1.0 (administrative data sync)"})
    print("Đang tải", URL)
    with urlopen(req, timeout=50) as stream:
        content = stream.read(12 * 1024 * 1024 + 1)
    if len(content) > 12 * 1024 * 1024:
        raise ValueError("Nguồn vượt 12 MiB")
    rows = transform(json.loads(content))
    compact = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=TARGET.parent, delete=False) as file:
        tmp = Path(file.name)
        file.write(compact)
        file.flush()
    tmp.replace(TARGET)
    metadata = {
        "title": "Vietnam Administrative Divisions",
        "source": URL,
        "license": "CC-BY-4.0",
        "source_last_reported_update": "2026-09-08",
        "downloaded_utc": datetime.now(timezone.utc).isoformat(),
        "sha256_raw": hashlib.sha256(content).hexdigest(),
        "sha256_compact": hashlib.sha256(compact).hexdigest(),
        "count": len(rows),
        "coordinate_precision": "Representative coordinates, not legal boundary polygons",
    }
    (TARGET.parent / "admin_provenance.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("OK:", len(rows), "đơn vị ->", TARGET, "sha256", metadata["sha256_compact"])


if __name__ == "__main__":
    main()
