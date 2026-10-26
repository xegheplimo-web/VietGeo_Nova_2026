"""Dependency-free localhost HTTP server for VietGeo Nova."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sqlite3
import subprocess
import sys
import threading
from contextlib import closing, contextmanager
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from . import __version__, osm
from . import db as storage

MAX_BYTES = 16 * 1024 * 1024
WEB = storage.ROOT / "web"

CSP = "; ".join(
    (
        "default-src 'self'",
        "script-src 'self' https://unpkg.com",
        "style-src 'self' https://unpkg.com 'unsafe-inline'",
        "img-src 'self' data: blob: https://tiles.openfreemap.org https://assets.openfreemap.com",
        "font-src 'self' data: https://tiles.openfreemap.org https://assets.openfreemap.com https://api.mapbox.com",
        "connect-src 'self' "
        "https://unpkg.com "
        "https://tiles.openfreemap.org "
        "https://assets.openfreemap.com "
        "https://overpass-api.de",
        "worker-src 'self' blob: https://unpkg.com",
        "object-src 'none'",
        "base-uri 'none'",
        "frame-ancestors 'none'",
        "form-action 'self'",
    )
)


class Handler(SimpleHTTPRequestHandler):
    server_version = "VietGeoNova/" + __version__

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def end_headers(self):
        self.send_header("Content-Security-Policy", CSP)
        super().end_headers()

    def log_message(self, format, *args):
        super().log_message(format, *args)

    def _send(
        self,
        status,
        obj,
        content_type="application/json; charset=utf-8",
        disposition=None,
    ):
        body = (
            obj
            if isinstance(obj, bytes)
            else (obj.encode("utf-8") if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False).encode("utf-8"))
        )
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Cache-Control",
            "no-store" if self.path.startswith("/api/") else "public, max-age=1800",
        )
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        if disposition:
            self.send_header("Content-Disposition", disposition)
        self.end_headers()
        if self.command != "HEAD":
            try:
                self.wfile.write(body)
            except BrokenPipeError:
                pass

    def _error(self, status, msg):
        self._send(status, {"error": msg})

    def _args(self):
        return {k: v[-1] for k, v in parse_qs(urlsplit(self.path).query, keep_blank_values=True).items()}

    def _data(self):
        length = int(self.headers.get("Content-Length", "-1"))
        if not 0 <= length <= MAX_BYTES:
            raise ValueError("Dữ liệu gửi lên vượt quá 16 MiB hoặc thiếu Content-Length")
        try:
            return json.loads(self.rfile.read(length))
        except (ValueError, UnicodeDecodeError) as e:
            raise ValueError("JSON không hợp lệ") from e

    def _write_allowed(self):
        origin = self.headers.get("Origin", "")
        host = self.headers.get("Host", "").lower()
        # Browser CSRF: only same-origin requests; non-browser clients may omit Origin.
        if origin:
            try:
                u = urlsplit(origin)
                if u.scheme not in ("http", "https") or u.netloc.lower() != host:
                    self._error(403, "Origin không được phép")
                    return False
            except ValueError:
                self._error(403, "Origin không hợp lệ")
                return False
        token = os.getenv("VIETGEO_API_TOKEN", "")
        if token:
            import hmac

            incoming = self.headers.get("Authorization", "")
            if not hmac.compare_digest(incoming, "Bearer " + token):
                self._error(401, "Cần Bearer token để ghi dữ liệu")
                return False
        return True

    @contextmanager
    def _db(self):
        with closing(storage.connect()) as connection, connection:
            yield connection

    def _revision(self, conn):
        conn.execute(
            "INSERT INTO metadata(key,value) VALUES('revision',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (storage.now(),),
        )

    def _host_allowed(self):
        # Docker publishes the port under arbitrary Host values (host IP, LAN);
        # VIETGEO_CONTAINER=1 is already required by main() to bind 0.0.0.0.
        if os.getenv("VIETGEO_CONTAINER") == "1":
            return True
        host = self.headers.get("Host", "")
        try:
            hostname = urlsplit("http://" + host).hostname
        except ValueError:
            hostname = None
        if hostname not in ("localhost", "127.0.0.1", "::1"):
            self._error(403, "Máy chủ chỉ cho phép truy cập bằng localhost hoặc 127.0.0.1")
            return False
        return True

    def do_GET(self):
        if not self._host_allowed():
            return
        path = urlsplit(self.path).path
        if not path.startswith("/api/"):
            # Avoid exposing local data via static-file path traversal.
            if path == "/":
                self.path = "/index.html"
            return super().do_GET()
        try:
            args = self._args()
            if path == "/api/health":
                return self._send(200, {"ok": True, "version": __version__, "mode": "localhost"})
            if path in ("/api/provinces", "/api/admin/provinces"):
                return self._send(
                    200,
                    {
                        "source": "open-admin-data / 2026-09-08 / CC-BY-4.0",
                        "items": storage.read_provinces(),
                    },
                )
            if path == "/api/admin/wards":
                file = storage.ROOT / "data" / "wards_3321.json"
                if not file.exists():
                    return self._send(
                        200,
                        {
                            "items": [],
                            "installed": False,
                            "hint": "Chạy py tools/sync_admin.py",
                        },
                    )
                units = json.loads(file.read_text(encoding="utf-8"))
                province = args.get("province", "")
                search = storage.ascii_fold(args.get("search", "").strip())
                if province:
                    units = [u for u in units if u["province_code"] == province]
                if search:
                    units = [u for u in units if search in storage.ascii_fold(u["name"])]
                return self._send(200, {"items": units[:1000], "installed": True, "total": len(units)})
            with self._db() as c:
                if path == "/api/stats":
                    n = c.execute("SELECT COUNT(*) FROM places").fetchone()[0]
                    bysource = [
                        dict(r)
                        for r in c.execute(
                            "SELECT source,COUNT(*) AS count FROM places GROUP BY source ORDER BY count DESC"
                        )
                    ]
                    bycat = [
                        dict(r)
                        for r in c.execute(
                            "SELECT category,COUNT(*) AS count FROM places GROUP BY category ORDER BY count DESC LIMIT 18"
                        )
                    ]
                    rev = c.execute("SELECT value FROM metadata WHERE key='revision'").fetchone()
                    sync = c.execute("SELECT value FROM metadata WHERE key='osm_imported_at'").fetchone()
                    return self._send(
                        200,
                        {
                            "places": n,
                            "by_source": bysource,
                            "categories": bycat,
                            "revision": rev[0] if rev else None,
                            "osm_imported_at": sync[0] if sync else None,
                        },
                    )
                if path == "/api/data/status":
                    f = storage.ROOT / "data" / "wards_3321.json"
                    return self._send(
                        200,
                        {
                            "provinces": 34,
                            "wards_installed": f.exists(),
                            "wards_expected": 3321,
                            "ward_source_last_updated": "2026-09-08",
                            "poi_coverage": "Only imported data; not a complete business registry",
                            "basemap": "Live OpenFreeMap vector tiles; requires Internet",
                        },
                    )
                if path == "/api/revision":
                    r = c.execute("SELECT value FROM metadata WHERE key='revision'").fetchone()
                    return self._send(200, {"revision": r[0] if r else None})
                if path == "/api/places" or path in (
                    "/api/export.geojson",
                    "/api/export.csv",
                ):
                    bbox = None
                    if args.get("bbox"):
                        try:
                            bbox = tuple(float(v) for v in args["bbox"].split(","))
                        except ValueError as e:
                            raise ValueError("bbox không hợp lệ") from e
                        if len(bbox) != 4:
                            raise ValueError("bbox cần 4 giá trị")
                    near = None
                    if args.get("near"):
                        try:
                            near = tuple(float(v) for v in args["near"].split(","))
                        except ValueError as e:
                            raise ValueError("near không hợp lệ") from e
                        if len(near) != 2:
                            raise ValueError("near cần lat,lon")
                        if bbox is None:
                            lat, lon = near
                            radius = float(args.get("radius_m", "10000"))
                            if not 0 < radius <= 100000:
                                raise ValueError("radius_m tối đa 100km")
                            latd = radius / 111000
                            lond = radius / (
                                111000
                                * max(
                                    0.1,
                                    abs(math.cos(math.radians(lat))),
                                )
                            )
                            bbox = (
                                max(-180, lon - lond),
                                max(-90, lat - latd),
                                min(180, lon + lond),
                                min(90, lat + latd),
                            )
                    radius = float(args.get("radius_m", "10000"))
                    if not 0 < radius <= 100000:
                        raise ValueError("radius_m tối đa 100km")
                    export = path.startswith("/api/export")
                    limit = min(20000, int(args.get("limit", "10000" if export else "300")))
                    if export and limit > 500:
                        # Export uses paged fetches, avoids silently truncating at query's UI cap.
                        allrows = []
                        for offset in range(0, limit, 500):
                            batch = storage.query(
                                c,
                                search=args.get("search", ""),
                                category=args.get("category", ""),
                                province=args.get("province", ""),
                                bbox=bbox,
                                near=near,
                                radius_m=radius,
                                limit=min(500, limit - offset),
                                offset=offset,
                            )
                            allrows.extend(batch)
                            if len(batch) < min(500, limit - offset):
                                break
                        rows = allrows
                    else:
                        rows = storage.query(
                            c,
                            search=args.get("search", ""),
                            category=args.get("category", ""),
                            province=args.get("province", ""),
                            bbox=bbox,
                            near=near,
                            radius_m=radius,
                            limit=limit,
                            offset=int(args.get("offset", "0")),
                        )
                    if path == "/api/export.geojson":
                        return self._send(
                            200,
                            storage.to_geojson(rows),
                            disposition='attachment; filename="vietgeo-nova.geojson"',
                        )
                    if path == "/api/export.csv":
                        return self._send(
                            200,
                            storage.to_csv(rows),
                            "text/csv; charset=utf-8",
                            disposition='attachment; filename="vietgeo-nova.csv"',
                        )
                    return self._send(
                        200,
                        {"items": rows, "count": len(rows), "limit": min(500, limit)},
                    )
                match = re.fullmatch(r"/api/places/(\d+)", path)
                if match:
                    r = c.execute("SELECT * FROM places WHERE id=?", (int(match[1]),)).fetchone()
                    if r:
                        return self._send(200, storage.serial(r))
                    return self._error(404, "Không tìm thấy địa điểm")
            return self._error(404, "Endpoint không tồn tại")
        except (ValueError, TypeError, OverflowError) as e:
            self._error(400, str(e))
        except sqlite3.Error as e:
            self._error(500, "Lỗi truy vấn SQLite: " + str(e))

    def do_POST(self):
        if not self._host_allowed() or not self._write_allowed():
            return
        path = urlsplit(self.path).path
        try:
            data = self._data()
            if path == "/api/osm/area":
                if not isinstance(data, dict) or not isinstance(data.get("bbox"), list):
                    raise ValueError("Cần bbox 4 tọa độ")
                return self._send(200, osm.import_small_area(data["bbox"]))
            with self._db() as c:
                if path == "/api/places":
                    if not isinstance(data, dict):
                        raise ValueError("Cần JSON object")
                    id, changed = storage.upsert(c, data, source="user")
                    self._revision(c)
                    result = {"id": id, "created": changed}
                    status = 201
                if path == "/api/import":
                    if isinstance(data, dict) and data.get("type") == "FeatureCollection":
                        features = data.get("features")
                        if not isinstance(features, list) or len(features) > 10000:
                            raise ValueError("Tối đa 10.000 điểm một lần")
                        data = []
                        for f in features:
                            geo = f.get("geometry") or {}
                            if (
                                geo.get("type") != "Point"
                                or not isinstance(geo.get("coordinates"), list)
                                or len(geo["coordinates"]) < 2
                            ):
                                raise ValueError("GeoJSON import chỉ hỗ trợ Point")
                            p = dict(f.get("properties") or {})
                            p.update(lon=geo["coordinates"][0], lat=geo["coordinates"][1])
                            data.append(p)
                    if not isinstance(data, list) or len(data) > 10000:
                        raise ValueError("Cần array hoặc FeatureCollection tối đa 10.000 điểm")
                    # Every import batch is atomic; failures roll back all records.
                    inserted = 0
                    for row in data:
                        _, changed = storage.upsert(c, row, source="user")
                        inserted += int(changed)
                    if inserted:
                        self._revision(c)
                    result = {"imported": inserted, "records": len(data)}
                    status = 200
                if path not in ("/api/places", "/api/import"):
                    return self._error(404, "Endpoint không tồn tại")
            return self._send(status, result)
        except (ValueError, TypeError) as e:
            self._error(400, str(e))
        except sqlite3.Error:
            self._error(500, "Lỗi ghi cơ sở dữ liệu")

    def do_PUT(self):
        if not self._host_allowed() or not self._write_allowed():
            return
        path = urlsplit(self.path).path
        match = re.fullmatch(r"/api/places/(\d+)", path)
        if not match:
            return self._error(404, "Endpoint không tồn tại")
        try:
            payload = storage.normalize(self._data(), force_source="user")
            with self._db() as c:
                prior = c.execute("SELECT source FROM places WHERE id=?", (int(match[1]),)).fetchone()
                if not prior:
                    return self._error(404, "Không tìm thấy")
                if prior["source"] != "user":
                    return self._error(403, "Không chỉnh sửa trực tiếp bản ghi OSM. Tạo bản ghi riêng.")
                setters = ",".join(f"{k}=?" for k in payload)
                c.execute(
                    "UPDATE places SET " + setters + " WHERE id=?",
                    (*payload.values(), int(match[1])),
                )
                self._revision(c)
            return self._send(200, {"ok": True})
        except (ValueError, TypeError) as e:
            self._error(400, str(e))

    def do_DELETE(self):
        if not self._host_allowed() or not self._write_allowed():
            return
        match = re.fullmatch(r"/api/places/(\d+)", urlsplit(self.path).path)
        if not match:
            return self._error(404, "Endpoint không tồn tại")
        with self._db() as c:
            result = c.execute("DELETE FROM places WHERE id=? AND source='user'", (int(match[1]),))
            if result.rowcount:
                self._revision(c)
        return self._send(200 if result.rowcount else 403, {"deleted": bool(result.rowcount)})


def main():
    parser = argparse.ArgumentParser(description="VietGeo Nova localhost server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if args.host not in ("127.0.0.1", "localhost", "::1") and (
        args.host != "0.0.0.0" or os.getenv("VIETGEO_CONTAINER") != "1"
    ):
        raise SystemExit("Chỉ cho phép localhost, trừ chế độ Docker VIETGEO_CONTAINER=1")
    with closing(storage.connect()) as c:
        print("Địa điểm hiện có:", c.execute("SELECT COUNT(*) FROM places").fetchone()[0])
    if os.getenv("VIETGEO_AUTO_ADMIN_SYNC", "1") == "1" and not (storage.ROOT / "data" / "wards_3321.json").exists():

        def sync_admin_background():
            try:
                result = subprocess.run(
                    [sys.executable, str(storage.ROOT / "tools" / "sync_admin.py")],
                    check=False,
                    cwd=str(storage.ROOT),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=90,
                )
                if result.returncode == 0:
                    print("Hành chính:", (result.stdout or "").strip(), flush=True)
                else:
                    print(
                        "Không đồng bộ được xã/phường (có thể chạy tools/sync_admin.py):",
                        (result.stderr or "").strip()[:300],
                        flush=True,
                    )
            except Exception as exc:
                print("Không đồng bộ được xã/phường:", exc, flush=True)

        threading.Thread(target=sync_admin_background, daemon=True, name="admin-sync").start()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    srv.daemon_threads = True
    print(f"VietGeo Nova: http://{args.host}:{args.port} — Ctrl+C để dừng")
    try:
        srv.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
