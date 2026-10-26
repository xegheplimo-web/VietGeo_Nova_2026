"""Safe Geofabrik PBF downloader: stream, size guard, SHA-256 provenance, atomic rename."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "https://download.geofabrik.de/asia/vietnam-latest.osm.pbf"
TARGET = ROOT / "data" / "vietnam-latest.osm.pbf"


def main():
    p = argparse.ArgumentParser(description="Tải dữ liệu OpenStreetMap PBF Việt Nam từ Geofabrik")
    p.add_argument("--out", type=Path, default=TARGET)
    p.add_argument("--force", action="store_true")
    args = p.parse_args()
    dest = args.out.resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not args.force:
        print("PBF đã tồn tại:", dest, "; --force để tải mới")
        return
    req = Request(SOURCE, headers={"User-Agent": "VietGeoNova/1.0 (individual user PBF sync)"})
    with urlopen(req, timeout=90) as source:
        total = int(source.headers.get("Content-Length") or 0)
        if total > 2 * 1024**3:
            raise ValueError("Nguồn vượt 2 GiB")
        print(
            "Đang tải PBF",
            round(total / 1024**2, 1),
            "MiB (nếu server công bố dung lượng)",
        )
        h = hashlib.sha256()
        count = 0
        with tempfile.NamedTemporaryFile(dir=dest.parent, delete=False, suffix=".part") as file:
            tmp = Path(file.name)
            try:
                while True:
                    block = source.read(1024 * 1024)
                    if not block:
                        break
                    file.write(block)
                    h.update(block)
                    count += len(block)
                    if count > 2 * 1024**3:
                        raise ValueError("Nguồn vượt giới hạn 2 GiB")
                    if count % (32 * 1024 * 1024) == 0:
                        print("  ", round(count / 1024**2), "MiB...", flush=True)
            except BaseException:
                file.close()
                tmp.unlink(missing_ok=True)
                raise
    if total and count != total:
        tmp.unlink(missing_ok=True)
        raise ValueError("Tải chưa đủ Content-Length")
    if count < 10 * 1024 * 1024:
        tmp.unlink(missing_ok=True)
        raise ValueError("PBF quá nhỏ, nguồn có thể bị lỗi")
    tmp.replace(dest)
    meta = {
        "source": SOURCE,
        "license": "ODbL-1.0",
        "retrieved_utc": datetime.now(UTC).isoformat(),
        "size_bytes": count,
        "sha256": h.hexdigest(),
        "last_modified": source.headers.get("Last-Modified"),
    }
    (dest.with_name(dest.name + ".provenance.json")).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("OK:", dest, "size=", count, "sha256=", h.hexdigest())


if __name__ == "__main__":
    main()
