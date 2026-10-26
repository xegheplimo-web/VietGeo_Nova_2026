# VietGeo Nova 2026 — bản đồ Việt Nam độc lập, hiện đại, local-first

> **Dự án hoàn toàn mới, độc lập**: không phụ thuộc hoặc sử dụng mã nguồn, cơ sở dữ liệu, API hay cấu hình của bất kỳ dự án bản đồ trước đây nào.
>
> **Phiên bản:** 1.0.0 · **Đóng gói:** 27/10/2026 · **Nền tảng:** Python 3.10+, Windows 11 / Linux / macOS / Docker.

## 1. Khởi chạy trên Windows 11

1. Giải nén toàn bộ ZIP vào một thư mục có quyền ghi, ví dụ `D:\VietGeo_Nova_2026`.
2. Cài **Python 3.10+** từ https://www.python.org/downloads/ và bật `Add python.exe to PATH` (nếu chưa cài).
3. Nhấp đúp **`START_WINDOWS.bat`**.
4. Vào **http://127.0.0.1:8765** trong Chrome/Edge; nếu trình duyệt mở sớm, tải lại trang.

Không cần `pip install` để khởi chạy backend. **Cần Internet để thấy nền bản đồ vector và để tải các nguồn dữ liệu mới.** Cần trình duyệt hỗ trợ WebGL2.

Khi khởi động lần đầu, máy chủ *thử* đồng bộ 3.321 xã/phường từ nguồn mở vào `data/wards_3321.json`; nếu bị firewall chặn, vẫn xem được 34 tỉnh/thành đã đóng gói. Tự đồng bộ lại: `py tools\sync_admin.py --force`.

**Dùng Docker**: `docker compose up --build -d` rồi vào http://127.0.0.1:8765. Dữ liệu SQLite trong Docker được lưu riêng tại volume `vietgeo_runtime`; khác tệp SQLite khi chạy trực tiếp Windows.

## 2. Chức năng thực sự có trong ZIP

| Nhóm | Đã triển khai | Giới hạn thực tế |
|---|---|---|
| MapLibre GL JS 6.15.0 / WebGL2 | Bản đồ vector, xoay/nghiêng góc nhìn, zoom, scale, đổi kiểu nền sáng/tối | Tile/style lấy online từ OpenFreeMap. Góc nhìn nghiêng không đồng nghĩa địa hình/nhà 3D thật. |
| Giao diện | Dashboard tối, responsive desktop/mobile, popup an toàn, bản đồ & danh sách đồng bộ | Phải cho phép CDN MapLibre nếu mạng chặn |
| Địa điểm | Tìm kiếm **không dấu**, FTS5, lọc danh mục/tỉnh/vùng, cluster, tọa độ, đánh dấu yêu thích, GPS gần tôi, mở chỉ đường | Dữ liệu có trong SQLite, không tự có mọi điểm kinh doanh |
| Quản lý | Thêm/sửa/xóa POI tự tạo, ghi nguồn và OSM ID; SQLite bền vững, sao lưu | Chỉ hỗ trợ điểm (Point), không phải polygon đầy đủ |
| Dữ liệu hành chính | **34 tỉnh/thành** có tọa độ đại diện nằm ngay trong ZIP; công cụ cập nhật **3.321 xã/phường** | Xã/phường tải khi chạy (không nhúng sẵn); tọa độ **không phải ranh giới pháp lý** |
| OSM trực tiếp | Nút **Nạp OSM vùng** gọi Overpass cho khu vực nhỏ, nhập POI node/way/relation | Rate-limit 60 giây/lượt và diện tích ≤ 0,25 độ vuông; tùy khả dụng Overpass |
| OSM toàn quốc | Công cụ tải `vietnam-latest.osm.pbf` từ Geofabrik; nhập POI node/way vào SQLite, cập nhật theo ID | PBF hàng trăm MB, **không có trong ZIP**; importer cần `osmium` |
| API | REST JSON / GeoJSON / CSV, CRUD, tìm kiếm theo bbox/near, metadata, nguồn hành chính | Localhost only, không triển khai Internet production mặc định |
| Bảo mật | Kiểm tra Origin/Host, giới hạn kích thước JSON, SQL tham số hóa, chặn CSV formula, chống chèn HTML qua textContent | Muốn public cần thêm người dùng/quyền, HTTPS, quota, kiểm thử bảo mật |
| Đồng bộ | Revision polling nhiều tab ~12 giây, người dùng có thể nhập CSV/GeoJSON | Không phải multi-user realtime bằng WebSocket |
| Kiểm thử | Test SQLite, RTree, FTS tìm không dấu, API CRUD, bảo mật, nhập dữ liệu nguyên tử, Overpass mô phỏng | Thử nghiệm Internet/end-to-end WebGL thật cần thực hiện ở máy người dùng |

## 3. Nạp dữ liệu địa điểm mới nhất

**Lựa chọn nhẹ nhất:** mở giao diện, zoom vào một phường/quận, nhấn **Nạp OSM vùng**. Hệ thống lấy POI có tên từ API Overpass công khai, đưa vào SQLite theo ID OSM để tránh trùng. Overpass có thể từ chối hoặc chậm; đây không phải dịch vụ có SLA. Không nhấn quét hàng loạt.

**Lựa chọn toàn quốc (khuyến nghị khi cần nhiều POI):** đóng server trước khi nhập lượng lớn, mở Terminal tại thư mục dự án:

```powershell
py -m pip install osmium
py tools/download_osm.py
py tools/import_osm.py
py tools/backup.py
```

- Có thể nhấp đúp `UPDATE_DATA_WINDOWS.bat`: tải lại 3.321 xã/phường, sau đó **hỏi xác nhận** trước khi tải PBF và nhập toàn quốc.
- `tools/download_osm.py --force` cập nhật PBF từ nguồn mới. Mỗi lần tải có provenance SHA-256, ngày truy xuất, dung lượng và Last-Modified (nếu máy chủ cung cấp).
- `tools/import_osm.py` xử lý **node/way** POI theo OSM ID (centroid xấp xỉ cho way). Trong tương lai cần một importer chuyên dụng để nhập relation đầy đủ, cập nhật diff theo phút, topo/polygon và data-warehouse cấp doanh nghiệp.
- Bộ importer **không gán tỉnh/xã bằng suy đoán tọa độ**, do chưa có bộ polygon pháp lý được kiểm định. Có thể tìm theo tên tỉnh nếu bản ghi OSM có `addr:province`.
- Dữ liệu liên kết `source_url`, `tags` và thời điểm cập nhật; không xác minh 100% cửa hàng còn hoạt động hay thông tin pháp nhân.

**Quyền sử dụng dữ liệu:** không scrape hàng loạt Google Maps, không tự gắn nhãn 'dữ liệu đăng ký kinh doanh chính thức'. Nguồn POI OSM là dữ liệu cộng đồng theo ODbL.

## 4. Nhập/xuất, quản lý và bảo mật

**CSV nhập:** `name,lat,lon` bắt buộc; có thể thêm `category,address,province,source_url`. Dấu nháy kép và dấu phẩy trong chuỗi được xử lý. Tối đa 10.000 điểm/lượt import, 15 MiB/tệp trong giao diện; backend 16 MiB/request. GeoJSON chỉ hỗ trợ `FeatureCollection` với geometry `Point`.

**Xuất:** nhấn “Xuất dữ liệu” cho GeoJSON tối đa 20.000 điểm/lần, hoặc truy cập `http://127.0.0.1:8765/api/export.csv?limit=20000` để xuất CSV. Dữ liệu lớn hơn cần export theo phân trang hoặc pipeline chuyên dụng.

**Thêm POI:** nhấn “Thêm địa điểm”, chọn tọa độ bằng cách bấm lên bản đồ rồi điền tên, danh mục, địa chỉ. Chỉ địa điểm do người dùng tự tạo (`source=user`) mới sửa/xóa được trong UI. POI OSM được cập nhật thông qua nguồn.

**Sao lưu:** `py tools/backup.py` tạo bản backup có kiểm tra `PRAGMA integrity_check` vào `backups/`. Giữ ít nhất 2 bản backup khi cập nhật toàn quốc.

**Bearer token tùy chọn cho API ghi:** chạy PowerShell trong thư mục dự án:

```powershell
$env:VIETGEO_API_TOKEN='CHON_MOT_TOKEN_DAI_KHO_DOAN'
py -m vietgeo.server
```

Khi bật token, mở form thêm địa điểm và điền token vào ô API Token để gửi yêu cầu ghi từ trình duyệt. Đây là **ứng dụng local-first**, không phải hệ thống tài khoản công khai. Docker chỉ công bố port cho `127.0.0.1`; không chuyển cổng ra Internet.

## 5. API mẫu

```text
GET  /api/health
GET  /api/data/status
GET  /api/stats
GET  /api/provinces
GET  /api/admin/wards?province=01
GET  /api/places?search=benh+vien&province=H%C3%A0+N%E1%BB%99i&limit=100
GET  /api/places?bbox=105.7,20.9,105.9,21.2&category=Y%20t%E1%BA%BF
GET  /api/places?near=21.0285,105.8542&radius_m=3000
GET  /api/places/{id}
POST /api/places              JSON: {"name":"...","lat":21,"lon":105}
PUT  /api/places/{id}         JSON: đầy đủ trường của POI tự tạo
DELETE /api/places/{id}
POST /api/import              JSON: array hoặc GeoJSON FeatureCollection
POST /api/osm/area            JSON: {"bbox":[105.7,20.9,105.8,21.0]}
GET  /api/export.geojson?limit=20000
GET  /api/export.csv?limit=20000
```

**Cơ sở dữ liệu:** `data/vietgeo.sqlite3` (Windows/Python trực tiếp). Tự tạo khi lần đầu chạy. Dữ liệu không đến từ bất kỳ ứng dụng bản đồ cũ nào.

## 6. Kiểm thử và cấu trúc

```powershell
py -m unittest discover -s tests -v
```

```text
vietgeo/             Backend HTTP Python và SQLite; module OSM
web/                 HTML/CSS/JS giao diện MapLibre
 data/provinces_34.json   34 tỉnh/thành (đóng gói)
tools/sync_admin.py  Đồng bộ 3.321 xã/phường vào data/
tools/download_osm.py  Tải PBF, tính SHA256
tools/import_osm.py Nhập POI vào SQLite bằng pyosmium
tools/backup.py     Sao lưu an toàn
 tests/             Test offline
Dockerfile, compose.yaml, START_WINDOWS.bat, UPDATE_DATA_WINDOWS.bat
```

## 7. Phạm vi dữ liệu và giấy phép

- **Hành chính:** `open-admin-data/vietnam-administrative-divisions`, **CC BY 4.0**, báo cập nhật gần nhất **08/09/2026**, gồm 34 tỉnh/thành & 3.321 xã/phường, tọa độ đại diện. Xem `docs/SOURCES_AND_LICENSES.md`. Tệp 34 tỉnh đã chuyển thành định dạng gọn, có ghi công nguồn.
- **OSM:** Geofabrik Việt Nam (dữ liệu OSM theo thời điểm tải), **ODbL 1.0**, bắt buộc ghi công người đóng góp khi hiển thị và xử lý dữ liệu phát sinh. Không nhúng PBF hoặc dữ liệu doanh nghiệp thương mại vào ZIP.
- **Bản đồ nền:** OpenFreeMap sử dụng trực tuyến, không tải hàng loạt tile, tuân thủ điều khoản nhà cung cấp; nếu cần offline/private phải self-host tile server hoặc mua nhà cung cấp phù hợp.
- **MapLibre GL JS:** thư viện mã nguồn mở từ CDN theo giấy phép BSD-3-Clause; phần ứng dụng Python/JS tự tạo phân phối MIT trong `LICENSE`.

### Chưa có trong bản phát hành này

Không có bản đồ ngoại tuyến toàn quốc (PMTiles/MBTiles), điều hướng turn-by-turn nội bộ, street view, dữ liệu doanh nghiệp chính thức toàn diện, ranh giới địa chính/cấp xã dạng polygon được kiểm định, dữ liệu ảnh vệ tinh thương mại, hoặc khả năng xác minh mọi POI là mới nhất theo thời gian thực. Các tính năng này đòi hỏi dữ liệu/giấy phép/hạ tầng riêng và **không nên được tuyên bố là có** khi chưa triển khai.
