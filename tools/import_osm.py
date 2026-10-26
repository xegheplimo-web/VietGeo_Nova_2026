"""Streaming OSM PBF POI importer via pyosmium (only optional dependency).
Imports real named nodes/ways, uses average node coordinates for ways. This is NOT
an address geocoder or a legal-administration spatial join.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vietgeo import db, osm

try:
    import osmium
except ImportError:
    raise SystemExit("Thiếu pyosmium: chạy py -m pip install osmium (hoặc python -m pip install osmium)") from None


class Ingest(osmium.SimpleHandler):
    def __init__(self, conn, limit=0):
        super().__init__()
        self.c = conn
        self.limit = limit
        self.scanned = 0
        self.imported = 0
        self.skipped = 0

    def store(self, kind, identifier, tags, lat, lon):
        if self.limit and self.scanned >= self.limit:
            return
        self.scanned += 1
        try:
            projected = osm.project(kind, identifier, dict(tags), lat, lon)
            if projected:
                item, ref = projected
                _, changed = db.upsert(self.c, item, external_id=ref, source="osm")
                self.imported += int(changed)
                if self.imported % 1000 == 0 and changed:
                    self.c.commit()
                    print(
                        f"Nhập: {self.imported:,} / đã quét {self.scanned:,}",
                        flush=True,
                    )
            else:
                self.skipped += 1
        except (ValueError, sqlite3.IntegrityError):
            self.skipped += 1

    def node(self, n):
        if not n.tags or not n.location.valid():
            return
        if not any(k in n.tags for k in osm.TAGS):
            return
        self.store("node", n.id, n.tags, float(n.location.lat), float(n.location.lon))

    def way(self, w):
        if not w.tags or not any(k in w.tags for k in osm.TAGS):
            return
        valid = [n.location for n in w.nodes if n.location.valid()]
        if not valid:
            return
        lat = sum(float(p.lat) for p in valid) / len(valid)
        lon = sum(float(p.lon) for p in valid) / len(valid)
        self.store("way", w.id, w.tags, lat, lon)


def main():
    p = argparse.ArgumentParser(description="Nhập POI node/way từ PBF toàn Việt Nam vào SQLite")
    p.add_argument("pbf", type=Path, nargs="?", default=db.ROOT / "data" / "vietnam-latest.osm.pbf")
    p.add_argument("--limit", type=int, default=0, help="0=không giới hạn; dùng để smoke test")
    args = p.parse_args()
    if not args.pbf.is_file():
        raise SystemExit("Chưa có PBF: python tools/download_osm.py")
    with closing(db.connect()) as c, c:
        h = Ingest(c, max(0, args.limit))
        print("Bắt đầu nhập dữ liệu PBF:", args.pbf)
        h.apply_file(str(args.pbf), locations=True, idx="flex_mem")
        c.execute(
            "INSERT INTO metadata(key,value) VALUES('osm_imported_at',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (db.now(),),
        )
        c.execute(
            "INSERT INTO metadata(key,value) VALUES('revision',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (db.now(),),
        )
        print(
            "Xong: inserted/updated=",
            h.imported,
            "seen=",
            h.scanned,
            "skipped=",
            h.skipped,
        )
    print(
        "Chú ý: importer không xử lý relation và không suy ra tỉnh/xã từ polygon. Ngõ/đường hiển thị qua vector basemap."
    )


if __name__ == "__main__":
    main()
