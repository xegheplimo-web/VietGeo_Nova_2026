"""OSM tag projection and public Overpass area import. OpenStreetMap database: ODbL 1.0."""

from __future__ import annotations

import json
import math
import threading
import time
from contextlib import closing
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from . import db

# Keep categories stable for long-term indexing and low-cardinality filters.
MAP = {
    "amenity": {
        "restaurant": "Ẩm thực",
        "cafe": "Ẩm thực",
        "fast_food": "Ẩm thực",
        "bar": "Ẩm thực",
        "pub": "Ẩm thực",
        "hospital": "Y tế",
        "clinic": "Y tế",
        "pharmacy": "Y tế",
        "doctors": "Y tế",
        "dentist": "Y tế",
        "school": "Giáo dục",
        "university": "Giáo dục",
        "college": "Giáo dục",
        "kindergarten": "Giáo dục",
        "bus_station": "Giao thông",
        "parking": "Giao thông",
        "fuel": "Giao thông",
        "charging_station": "Giao thông",
        "police": "Công cộng",
        "fire_station": "Công cộng",
        "post_office": "Công cộng",
        "library": "Công cộng",
        "bank": "Dịch vụ",
        "atm": "Dịch vụ",
        "marketplace": "Mua sắm",
        "place_of_worship": "Công cộng",
    },
    "shop": "Mua sắm",
    "tourism": "Du lịch",
    "leisure": "Thể thao",
    "office": "Dịch vụ",
    "healthcare": "Y tế",
    "public_transport": "Giao thông",
    "historic": "Du lịch",
}
TAGS = (
    "amenity",
    "shop",
    "tourism",
    "leisure",
    "office",
    "healthcare",
    "public_transport",
    "historic",
)
_lock = threading.Lock()
_last_requested = 0.0


def category(tags: dict) -> str:
    for key in TAGS:
        if key in tags:
            rules = MAP.get(key)
            return (rules.get(tags[key], "Dịch vụ") if isinstance(rules, dict) else rules) or "Khác"
    return "Khác"


def project(osm_type: str, osm_id: int, tags: dict, lat: float, lon: float) -> tuple[dict, str] | None:
    name = str(tags.get("name:vi") or tags.get("name") or tags.get("brand") or "").strip()
    if not name or len(name) > 250 or not any(k in tags for k in TAGS):
        return None
    if not (math.isfinite(lat) and math.isfinite(lon) and 7.5 <= lat <= 24.5 and 100 <= lon <= 112):
        return None
    address = " ".join(str(tags.get(k, "")).strip() for k in ("addr:housenumber", "addr:street") if tags.get(k))
    if not address:
        address = str(tags.get("addr:full", "") or "").strip()
    province = str(tags.get("addr:province", "") or "").strip()
    ref = f"osm:{osm_type}:{int(osm_id)}"
    fields = {
        str(k): str(v)
        for k, v in tags.items()
        if isinstance(k, str) and isinstance(v, (str, int, float)) and len(k) < 100 and len(str(v)) < 500
    }
    return {
        "name": name,
        "category": category(tags),
        "address": address,
        "province": province,
        "lat": lat,
        "lon": lon,
        "source_url": f"https://www.openstreetmap.org/{osm_type}/{int(osm_id)}",
        "tags": fields,
        "verified": False,
    }, ref


def from_overpass(item: dict):
    kind = item.get("type")
    osm_id = item.get("id")
    if kind not in ("node", "way", "relation") or not isinstance(osm_id, int):
        return None
    tags = item.get("tags") or {}
    pos = item if kind == "node" else (item.get("center") or {})
    try:
        return project(kind, osm_id, tags, float(pos["lat"]), float(pos["lon"]))
    except (TypeError, ValueError, KeyError):
        return None


def import_small_area(bbox: list[float], max_items: int = 2500) -> dict:
    """Explicit user-initiated small city-area OSM fetch, not a nationwide scraper."""
    global _last_requested
    if len(bbox) != 4:
        raise ValueError("bbox phải có 4 giá trị")
    w, s, e, n = map(float, bbox)
    if not all(map(math.isfinite, (w, s, e, n))) or not (100 <= w < e <= 112 and 7.5 <= s < n <= 24.5):
        raise ValueError("Vùng nhập phải ở Việt Nam và đúng thứ tự bbox")
    if (e - w) * (n - s) > 0.25:
        raise ValueError("Vùng quá lớn: hãy phóng to bản đồ (<= 0.25 độ vuông)")
    with _lock:
        if time.monotonic() - _last_requested < 60:
            raise ValueError("Overpass đang được giới hạn: mỗi 60 giây tối đa một yêu cầu")
        _last_requested = time.monotonic()
    statement = "".join(f'nwr["name"]["{key}"]({s:.6f},{w:.6f},{n:.6f},{e:.6f});' for key in TAGS)
    q = f"[out:json][timeout:25];({statement});out center {int(max_items)};"
    data = urlencode({"data": q}).encode("utf-8")
    request = Request(
        "https://overpass-api.de/api/interpreter",
        data=data,
        headers={
            "User-Agent": "VietGeoNova/1.0 (user-initiated geographic data viewer)",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=38) as reply:
            raw = reply.read(10 * 1024 * 1024 + 1)
            if len(raw) > 10 * 1024 * 1024:
                raise ValueError("Phản hồi Overpass quá lớn")
            elements = json.loads(raw)["elements"]
    except (HTTPError, URLError, TimeoutError, KeyError, ValueError) as exc:
        raise ValueError("Máy chủ Overpass không trả dữ liệu: " + str(exc)[:220]) from exc
    imported = 0
    with closing(db.connect()) as c, c:
        for item in elements:
            record = from_overpass(item)
            if record:
                payload, ref = record
                _, changed = db.upsert(c, payload, external_id=ref, source="osm")
                imported += int(changed)
        if imported:
            stamp = db.now()
            c.execute(
                "INSERT INTO metadata(key,value) VALUES('revision',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (stamp,),
            )
            c.execute(
                "INSERT INTO metadata(key,value) VALUES('osm_imported_at',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (stamp,),
            )
    return {
        "imported": imported,
        "fetched": len(elements),
        "truncated": len(elements) >= max_items,
        "provider": "Overpass / OSM / ODbL",
    }
