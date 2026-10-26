"""Stand-alone smoke and API correctness gates. No external network required."""

import io
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from vietgeo import db, osm
from vietgeo.server import Handler, ThreadingHTTPServer


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.c = db.connect(Path(self.tmp.name) / "test.sqlite3")

    def tearDown(self):
        self.c.close()
        self.tmp.cleanup()

    def test_administrative_provinces(self):
        p = db.read_provinces()
        self.assertEqual(len(p), 34)
        self.assertEqual(sum(x["wards"] for x in p), 3321)
        self.assertEqual(p[0]["name"], "Hà Nội")

    def test_accentless_search_and_injection(self):
        db.upsert(
            self.c,
            {
                "name": "Bệnh viện Đà Nẵng",
                "lat": 16.07,
                "lon": 108.22,
                "category": "Y tế",
            },
        )
        self.assertEqual(len(db.query(self.c, search="Benh vien Da Nang")), 1)
        self.assertEqual(db.query(self.c, search='" OR 1=1 --'), [])

    def test_rtree_bbox_and_update(self):
        i, _ = db.upsert(self.c, {"name": "Quán cà phê thử", "lat": 10.8, "lon": 106.7})
        self.assertEqual(len(db.query(self.c, bbox=(106.6, 10.7, 106.8, 10.9))), 1)
        self.c.execute("UPDATE places SET lon=105.9 WHERE id=?", (i,))
        self.assertEqual(db.query(self.c, bbox=(106.6, 10.7, 106.8, 10.9)), [])

    def test_near_order_correct_before_limit(self):
        db.upsert(self.c, {"name": "Gần nhất", "lat": 21.001, "lon": 105.8})
        for i in range(8):
            db.upsert(self.c, {"name": f"Xa {i}", "lat": 21.04 + i * 0.001, "lon": 105.8})
        res = db.query(
            self.c,
            near=(21, 105.8),
            bbox=(105.7, 20.9, 105.9, 21.2),
            radius_m=15000,
            limit=2,
        )
        self.assertEqual(res[0]["name"], "Gần nhất")
        self.assertEqual(len(res), 2)
        self.assertLess(res[0]["distance_m"], res[1]["distance_m"])

    def test_provenance_preserves_user(self):
        id, _ = db.upsert(
            self.c,
            {"name": "My place", "lat": 21, "lon": 106},
            external_id="osm:node:123",
            source="user",
        )
        id2, updated = db.upsert(
            self.c,
            {"name": "Changed OSM", "lat": 22, "lon": 106},
            external_id="osm:node:123",
            source="osm",
        )
        self.assertFalse(updated)
        self.assertEqual(id, id2)
        self.assertEqual(
            self.c.execute("SELECT name FROM places WHERE id=?", (id,)).fetchone()[0],
            "My place",
        )

    def test_invalid_coordinate(self):
        for value in ("nan", 92, "inf"):
            with self.assertRaises(ValueError):
                db.normalize({"name": "A", "lat": value, "lon": 106})

    def test_csv_formula_safety(self):
        i, _ = db.upsert(self.c, {"name": "=1+1", "lat": 21, "lon": 106})
        csv_data = db.to_csv([db.serial(self.c.execute("SELECT * FROM places WHERE id=?", (i,)).fetchone())])
        self.assertIn("'=1+1", csv_data)

    def test_osm_tags_and_projection(self):
        r = osm.project("node", 12, {"name": "Cơm tấm", "amenity": "restaurant"}, 10.8, 106.7)
        self.assertEqual(r[0]["category"], "Ẩm thực")
        self.assertEqual(r[1], "osm:node:12")
        self.assertIsNone(osm.project("node", 12, {"name": "Unnamed"}, 10.8, 106.7))


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.prev = os.environ.get("VIETGEO_DB")
        os.environ["VIETGEO_DB"] = str(Path(cls.tmp.name) / "live.sqlite3")
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.thread.join(timeout=2)
        if cls.prev is None:
            os.environ.pop("VIETGEO_DB", None)
        else:
            os.environ["VIETGEO_DB"] = cls.prev
        cls.tmp.cleanup()

    def call(self, path, method="GET", body=None, origin=None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        h = {"Content-Type": "application/json"}
        if origin:
            h["Origin"] = origin
        req = Request(self.base + path, data=data, method=method, headers=h)
        try:
            with urlopen(req, timeout=5) as res:
                return (
                    res.status,
                    json.loads(res.read())
                    if res.headers.get_content_type() == "application/json"
                    else res.read().decode(),
                )
        except HTTPError as e:
            return e.code, json.loads(e.read())

    def test_health_and_static(self):
        st, x = self.call("/api/health")
        self.assertEqual(st, 200)
        self.assertTrue(x["ok"])
        st, html = self.call("/")
        self.assertEqual(st, 200)
        self.assertIn("VietGeo Nova", html)
        st, provinces = self.call("/api/provinces")
        self.assertEqual(len(provinces["items"]), 34)

    def test_crud_and_search(self):
        payload = {
            "name": "Trường học Việt",
            "lat": 21.1,
            "lon": 105.8,
            "category": "Giáo dục",
        }
        st, x = self.call("/api/places", "POST", payload)
        self.assertEqual(st, 201)
        i = x["id"]
        self.assertGreater(i, 0)
        st, x = self.call("/api/places?search=truong%20hoc")
        self.assertEqual(st, 200)
        self.assertIn(i, [r["id"] for r in x["items"]])
        st, x = self.call(f"/api/places/{i}", "PUT", {**payload, "name": "Trường mới"})
        self.assertEqual(st, 200)
        st, x = self.call(f"/api/places/{i}", "DELETE")
        self.assertEqual(st, 200)
        self.assertTrue(x["deleted"])

    def test_origin_blocked(self):
        st, _x = self.call(
            "/api/places",
            "POST",
            {"name": "Block", "lat": 21, "lon": 105},
            origin="https://evil.invalid",
        )
        self.assertEqual(st, 403)

    def test_atomic_import(self):
        st, x = self.call(
            "/api/import",
            "POST",
            [
                {"name": "Should not save", "lat": 21, "lon": 105},
                {"name": "Bad", "lat": 999, "lon": 105},
            ],
        )
        self.assertEqual(st, 400)
        st, x = self.call("/api/places?search=Should%20not%20save")
        self.assertEqual(len(x["items"]), 0)

    def test_osm_invalid_bbox_no_network(self):
        st, _x = self.call("/api/osm/area", "POST", {"bbox": [100, 1, 103, 20]})
        self.assertEqual(st, 400)

    def test_overpass_mock(self):
        old = osm._last_requested
        osm._last_requested = 0
        raw = {
            "elements": [
                {
                    "type": "node",
                    "id": 992,
                    "lat": 21.2,
                    "lon": 105.8,
                    "tags": {"name": "Thử OSM", "amenity": "cafe"},
                }
            ]
        }
        with patch("vietgeo.osm.urlopen", return_value=io.BytesIO(json.dumps(raw).encode())):
            st, x = self.call("/api/osm/area", "POST", {"bbox": [105.7, 21, 105.9, 21.3]})
        osm._last_requested = old
        self.assertEqual(st, 200)
        self.assertEqual(x["imported"], 1)
        st, q = self.call("/api/places?search=Thu%20OSM")
        self.assertEqual(st, 200)
        self.assertEqual(q["items"][0]["name"], "Thử OSM")


if __name__ == "__main__":
    unittest.main()
