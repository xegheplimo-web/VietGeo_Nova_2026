"""SQLite storage for user and OSM POIs, FTS5, RTree and safe provenance."""

from __future__ import annotations

import csv
import io
import json
import math
import os
import re
import sqlite3
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "vietgeo.sqlite3"
SCHEMA = """
CREATE TABLE IF NOT EXISTS places (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 external_id TEXT UNIQUE, name TEXT NOT NULL, category TEXT NOT NULL DEFAULT 'other',
 address TEXT NOT NULL DEFAULT '', province TEXT NOT NULL DEFAULT '',
 lat REAL NOT NULL CHECK(lat BETWEEN -90 AND 90), lon REAL NOT NULL CHECK(lon BETWEEN -180 AND 180),
 source TEXT NOT NULL DEFAULT 'user', source_url TEXT NOT NULL DEFAULT '',
 verified INTEGER NOT NULL DEFAULT 0 CHECK(verified IN (0,1)),
 tags TEXT NOT NULL DEFAULT '{}', updated_at TEXT NOT NULL,
 search_norm TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_places_category ON places(category);
CREATE INDEX IF NOT EXISTS idx_places_province ON places(province);
CREATE INDEX IF NOT EXISTS idx_places_source ON places(source);
CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE VIRTUAL TABLE IF NOT EXISTS places_rtree USING rtree(id, min_lat, max_lat, min_lon, max_lon);
CREATE VIRTUAL TABLE IF NOT EXISTS places_fts USING fts5(search_norm, tokenize='unicode61 remove_diacritics 2');
CREATE TRIGGER IF NOT EXISTS places_ai AFTER INSERT ON places BEGIN
 INSERT INTO places_rtree VALUES (new.id,new.lat,new.lat,new.lon,new.lon);
 INSERT INTO places_fts(rowid,search_norm) VALUES (new.id,new.search_norm);
END;
CREATE TRIGGER IF NOT EXISTS places_ad AFTER DELETE ON places BEGIN
 DELETE FROM places_rtree WHERE id=old.id;
 DELETE FROM places_fts WHERE rowid=old.id;
END;
CREATE TRIGGER IF NOT EXISTS places_au AFTER UPDATE ON places BEGIN
 UPDATE places_rtree SET min_lat=new.lat,max_lat=new.lat,min_lon=new.lon,max_lon=new.lon WHERE id=old.id;
 DELETE FROM places_fts WHERE rowid=old.id;
 INSERT INTO places_fts(rowid,search_norm) VALUES (new.id,new.search_norm);
END;
"""
FIELDS = (
    "name",
    "category",
    "address",
    "province",
    "lat",
    "lon",
    "source",
    "source_url",
    "verified",
    "tags",
)


def ascii_fold(s: str) -> str:
    s = unicodedata.normalize("NFD", s.casefold()).replace("đ", "d")
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(db_path or os.getenv("VIETGEO_DB", str(DEFAULT_DB))).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=30000")
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    db.create_function("haversine_m", 4, haversine, deterministic=True)
    db.executescript(SCHEMA)
    return db


def normalize(data: dict, *, force_source: str | None = None) -> dict:
    if not isinstance(data, dict):
        raise ValueError("Record must be an object")
    name = str(data.get("name") or "").strip()
    if not (1 <= len(name) <= 250):
        raise ValueError("Tên địa điểm phải từ 1 đến 250 ký tự")
    try:
        lat, lon = float(data["lat"]), float(data["lon"])
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError("Tọa độ lat/lon không hợp lệ") from exc
    if not math.isfinite(lat) or not math.isfinite(lon) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Tọa độ vượt giới hạn")
    row = {
        key: str(data.get(key) or "").strip()[:600]
        for key in ("category", "address", "province", "source", "source_url")
    }
    row["category"] = row["category"] or "other"
    row["source"] = force_source or row["source"] or "user"
    if row["source_url"] and not row["source_url"].startswith(("https://", "http://")):
        raise ValueError("URL nguồn cần http(s)")
    tags = data.get("tags") or {}
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except json.JSONDecodeError as exc:
            raise ValueError("tags không phải JSON") from exc
    if not isinstance(tags, dict) or len(json.dumps(tags, ensure_ascii=False)) > 12000:
        raise ValueError("tags phải là đối tượng JSON tối đa 12 KB")
    row.update(
        name=name,
        lat=lat,
        lon=lon,
        verified=int(bool(data.get("verified", False))),
        tags=json.dumps(tags, ensure_ascii=False),
        updated_at=now(),
        search_norm=ascii_fold(" ".join((name, row["address"], row["province"], row["category"]))),
    )
    return row


def upsert(
    db: sqlite3.Connection,
    data: dict,
    *,
    external_id: str | None = None,
    source: str | None = None,
    preserve_verified: bool = True,
) -> tuple[int, bool]:
    row = normalize(data, force_source=source)
    if external_id is not None and len(external_id) > 200:
        raise ValueError("external_id dài quá 200 ký tự")
    if external_id:
        prior = db.execute("SELECT id,source,verified FROM places WHERE external_id=?", (external_id,)).fetchone()
        if prior:
            if preserve_verified and (prior["verified"] or prior["source"] == "user"):
                return prior["id"], False
            sets = ",".join(f"{k}=?" for k in row)
            db.execute(
                "UPDATE places SET " + sets + " WHERE id=?",
                (*row.values(), prior["id"]),
            )
            return prior["id"], True
    cols = ",".join((*row.keys(), "external_id"))
    vals = ",".join("?" for _ in range(len(row) + 1))
    cur = db.execute(f"INSERT INTO places ({cols}) VALUES ({vals})", (*row.values(), external_id))
    return cur.lastrowid, True


def serial(row: sqlite3.Row) -> dict:
    r = dict(row)
    r["verified"] = bool(r["verified"])
    try:
        r["tags"] = json.loads(r.get("tags") or "{}")
    except ValueError:
        r["tags"] = {}
    r.pop("search_norm", None)
    return r


def _tokens(q: str) -> str:
    # FTS5 string escaped as individual quoted prefix terms; avoid MATCH syntax injection.
    tokens = re.findall(r"\w+", ascii_fold(q), re.UNICODE)[:8]
    return " AND ".join('"' + token.replace('"', "") + '"*' for token in tokens if token)


def query(
    db: sqlite3.Connection,
    *,
    search: str = "",
    category: str = "",
    province: str = "",
    bbox: tuple[float, float, float, float] | None = None,
    limit: int = 200,
    offset: int = 0,
    near: tuple[float, float] | None = None,
    radius_m: float = 10000,
) -> list[dict]:
    limit = max(1, min(500, int(limit)))
    offset = max(0, min(1_000_000, int(offset)))
    clauses = []
    params = []
    joins = ""
    if bbox:
        w, s, e, n = bbox
        if not (-180 <= w <= 180 and -180 <= e <= 180 and -90 <= s <= 90 and -90 <= n <= 90 and w <= e and s <= n):
            raise ValueError("bbox phải là minLon,minLat,maxLon,maxLat")
        joins += " JOIN places_rtree r ON r.id=p.id"
        clauses += ["r.max_lon>=?", "r.min_lon<=?", "r.max_lat>=?", "r.min_lat<=?"]
        params.extend([w, e, s, n])
    if category and category != "all":
        clauses.append("p.category=?")
        params.append(category)
    if province:
        clauses.append("p.province=?")
        params.append(province)
    if near:
        lat, lon = near
        if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("near không hợp lệ")
        clauses.append("haversine_m(?,?,p.lat,p.lon)<=?")
        params.extend([lat, lon, radius_m])
    if search.strip():
        terms = _tokens(search)
        if terms:
            joins += " JOIN places_fts ON places_fts.rowid=p.id"
            clauses.append("places_fts MATCH ?")
            params.append(terms)
    sql = "SELECT p.* FROM places p" + joins + " WHERE " + (" AND ".join(clauses) if clauses else "1=1")
    sql += (
        " ORDER BY haversine_m(?,?,p.lat,p.lon) ASC, p.id DESC" if near else " ORDER BY p.id DESC"
    ) + " LIMIT ? OFFSET ?"
    order_params = [near[0], near[1]] if near else []
    try:
        rows = db.execute(sql, (*params, *order_params, limit, offset)).fetchall()
    except sqlite3.OperationalError:
        # FTS absent/corrupted => normalized fallback search.
        if not search.strip():
            raise
        joins = joins.replace(" JOIN places_fts ON places_fts.rowid=p.id", "")
        clauses = [c for c in clauses if c != "places_fts MATCH ?"]
        params = [v for v in params if v != _tokens(search)]
        clauses.append("p.search_norm LIKE ? ESCAPE '\\'")
        escaped = ascii_fold(search.strip()).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        params.append("%" + escaped + "%")
        order = " ORDER BY haversine_m(?,?,p.lat,p.lon) ASC, p.id DESC" if near else " ORDER BY p.id DESC"
        rows = db.execute(
            "SELECT p.* FROM places p" + joins + " WHERE " + " AND ".join(clauses) + order + " LIMIT ? OFFSET ?",
            (*params, *order_params, limit, offset),
        ).fetchall()
    results = [serial(r) for r in rows]
    if near:
        lat, lon = near
        for r in results:
            r["distance_m"] = round(haversine(lat, lon, r["lat"], r["lon"]))
    return results


def haversine(a, b, c, d) -> float:
    R = 6371008.8
    x = math.radians(c - a)
    y = math.radians(d - b)
    k = math.sin(x / 2) ** 2 + math.cos(math.radians(a)) * math.cos(math.radians(c)) * math.sin(y / 2) ** 2
    return 2 * R * math.asin(min(1.0, math.sqrt(k)))


def to_geojson(rows: list[dict]) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": r["id"],
                "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
                "properties": {k: v for k, v in r.items() if k not in ("lat", "lon")},
            }
            for r in rows
        ],
    }


def to_csv(rows: list[dict]) -> str:
    output = io.StringIO(newline="")
    fields = (
        "id",
        "name",
        "category",
        "address",
        "province",
        "lat",
        "lon",
        "source",
        "source_url",
        "verified",
        "updated_at",
    )
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        # Spreadsheet formula injection defense. Preserve underlying DB value.
        clean = {
            k: (
                ("'" + str(r.get(k, "")))
                if isinstance(r.get(k), str) and r[k].lstrip().startswith(("=", "+", "-", "@", "\t", "\r"))
                else r.get(k, "")
            )
            for k in fields
        }
        writer.writerow(clean)
    return output.getvalue()


def read_provinces() -> list[dict]:
    with (ROOT / "data" / "provinces_34.json").open(encoding="utf-8") as f:
        raw = json.load(f)
    return [{"code": r[0], "name": r[1], "lat": r[2], "lon": r[3], "wards": r[4]} for r in raw]


def backup(db: sqlite3.Connection, target: str | Path) -> None:
    with sqlite3.connect(str(target)) as dest:
        db.backup(dest)
