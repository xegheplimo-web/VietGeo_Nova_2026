# VietGeo Nova 2026 — Kiến trúc hiện đại hóa bản đồ

<badge color="success">Architecture decision: Offline-First Vector Maps</badge>

**Phán quyết: chọn một kiến trúc duy nhất — MapLibre GL JS + PMTiles + SQLite FTS5 + Valhalla (routing tùy chọn) — triển khai theo ba giai đoạn Q1 → Q2 → Q3.**

Mục tiêu không phải sao chép toàn bộ Google Maps. VietGeo phải đạt trải nghiệm bản đồ hiện đại, tìm kiếm địa điểm bằng tiếng Việt, hiển thị 3D và tìm đường, đồng thời vẫn hoạt động khi mất Internet.

## 1. Hiệu chỉnh dữ kiện trước khi quyết định

Có một điểm quan trọng cần sửa trong brief:

**OpenFreeMap hiện tại không phải nền bản đồ raster thuần túy.** OpenFreeMap sử dụng vector tiles theo schema OpenMapTiles. Bản README của VietGeo cũng mô tả MapLibre đang hiển thị vector basemap trực tuyến. Các tài nguyên raster như PNG có thể là sprite hoặc thành phần hình ảnh, không chứng minh basemap là raster. <Cite ref="turn361743view1"/>

Vì vậy, **không cần thay thế MapLibre hoặc xây lại rendering engine**. Việc cần làm là chuyển nguồn vector tiles online sang bộ dữ liệu vector lưu cục bộ.

<box border radius="lg" padding={3} gap={2}>
  <text color="secondary" weight="medium" size="xs">KIẾN TRÚC ĐÍCH</text>
  <box background="surface-secondary" padding={3} radius="md" align="center" gap={1}>
    **MapLibre GL JS + giao diện VietGeo**

    <text size="xs" color="secondary" textAlign="center">Vector basemap · POI · tìm kiếm · 3D · định tuyến</text>
  </box>
  <row justify="center">
    <icon name="arrow-down" color="secondary" size="lg"/>
  </row>
  <grid columns={2} gap={2}>
    <grid-item>
      <box border radius="md" padding={3} gap={1} height="100%">
        **Offline map**

        <text size="xs" color="secondary">PMTiles vector + MapLibre PMTiles protocol</text>
      </box>
    </grid-item>
    <grid-item>
      <box border radius="md" padding={3} gap={1} height="100%">
        **Local search**

        <text size="xs" color="secondary">SQLite FTS5 + RTree + chuẩn hóa tiếng Việt</text>
      </box>
    </grid-item>
    <grid-item>
      <box border radius="md" padding={3} gap={1} height="100%">
        **3D layers**

        <text size="xs" color="secondary">OSM building polygons + DEM offline</text>
      </box>
    </grid-item>
    <grid-item>
      <box border radius="md" padding={3} gap={1} height="100%">
        **Offline routing**

        <text size="xs" color="secondary">Valhalla sidecar Docker + OSM routing graph</text>
      </box>
    </grid-item>
  </grid>
  <row justify="center">
    <icon name="arrow-down" color="secondary" size="lg"/>
  </row>
  <box background="surface-secondary" radius="md" padding={3} align="center" gap={1}>
    **Python stdlib HTTP server + SQLite**

    <text size="xs" color="secondary" textAlign="center">Giữ zero Python runtime dependencies; phục vụ API và tài nguyên bản đồ cục bộ</text>
  </box>
</box>

<text color="secondary" size="xs">Routing sidecar không phải dependency bắt buộc để VietGeo khởi động. Pipeline tạo dữ liệu dùng công cụ riêng và không nằm trong backend runtime.</text>

---

## 2. Quyết định công nghệ cho từng chức năng

| Thành phần | Chọn duy nhất | Quyết định |
|---|---|---|
| Map engine | **MapLibre GL JS 6.x** | Giữ nguyên, đóng gói local |
| Vector basemap | **PMTiles v3** | Thay nguồn map online mặc định |
| Tile generator | **Planetiler + OpenMapTiles profile** | Chạy ngoài runtime |
| Map style | **OpenMapTiles-compatible style** | Giữ phong cách OpenFreeMap, sửa URL về local |
| POI database | **SQLite + FTS5 + RTree** | Giữ và nâng cấp |
| Geocoding | **FTS5 structured search** | Không cài Nominatim |
| Routing | **Valhalla Docker sidecar** | Tùy chọn, offline khi đã tạo graph |
| 3D buildings | **OSM building layer + fill-extrusion** | Dùng vector tiles đã tạo |
| Terrain | **DEM → Terrain-RGB → raster-dem** | Tải theo khu vực |
| Real-time traffic | **Không triển khai v1** | Không quảng bá traffic realtime |

### 2.1. Vector tiles: chọn Planetiler → MBTiles → PMTiles

Không chọn Tippecanoe làm bộ tạo basemap chính. Tippecanoe mạnh ở chuyển dữ liệu GeoJSON thành vector tiles, nhưng để xây basemap OSM đầy đủ còn phải xử lý cấu trúc đường, công trình, địa danh, polygon và schema.

Planetiler có OpenMapTiles profile, phù hợp hơn với phong cách bản đồ VietGeo hiện tại. <Cite refs={["turn613352search0","turn613352search4"]}/>

<box background="surface-secondary" padding={3} radius="lg" gap={2}>
  <text weight="medium" size="xs" color="secondary">PIPELINE TẠO DỮ LIỆU — KHÔNG CHẠY MỖI LẦN KHỞI ĐỘNG</text>
  <box align="center" gap={1}>
    **Geofabrik Vietnam `.osm.pbf`**

    <icon name="arrow-down" color="secondary"/>
    **Planetiler · OpenMapTiles profile**

    <icon name="arrow-down" color="secondary"/>
    **`vietnam.mbtiles`**

    <icon name="arrow-down" color="secondary"/>
    **`pmtiles convert`**

    <icon name="arrow-down" color="secondary"/>
    <box background="surface" border radius="md" padding={3} width="100%" align="center">
      **`vietnam.pmtiles`**

      <text color="secondary" size="xs">MapLibre đọc bằng PMTiles protocol qua HTTP Range</text>
    </box>
  </box>
</box>

Planetiler có thể cần thêm dữ liệu phụ như đường bờ biển, polygon đất liền, tên địa danh và các nguồn OpenMapTiles liên quan. Không nên tuyên bố chỉ một PBF là đủ tạo basemap hoàn chỉnh mọi zoom.

Lệnh chuyển đổi sau khi đã có MBTiles hợp lệ:

```bash
pmtiles convert vietnam.mbtiles vietnam.pmtiles
pmtiles verify vietnam.pmtiles
```

Công cụ PMTiles chính thức hỗ trợ chuyển đổi và xác minh archive. <Cite refs={["turn232812search4","turn361743search2"]}/>

**Chọn PMTiles thay vì phục vụ trực tiếp MBTiles** vì client MapLibre có thể đọc archive qua `addProtocol()`, không cần backend tile-rendering chuyên dụng. <Cite ref="turn346133search0"/>

Tuy nhiên, có một điều kiện kỹ thuật bắt buộc.

### 2.2. Python server phải hỗ trợ HTTP Range đúng chuẩn

`SimpleHTTPRequestHandler` không nên được giả định tự hỗ trợ byte-range request cần thiết cho PMTiles.

VietGeo cần bổ sung một đường dẫn chỉ đọc:

```text
GET  /offline/vietnam.pmtiles
HEAD /offline/vietnam.pmtiles
```

Ví dụ kết quả hợp lệ:

```http
HTTP/1.1 206 Partial Content
Accept-Ranges: bytes
Content-Range: bytes 0-16383/FILE_SIZE
Content-Length: 16384
Content-Type: application/octet-stream
```

Cần triển khai và kiểm thử `206`, `416`, range đầu/cuối file, `HEAD`, đường dẫn ngoài allowlist, nhiều request đồng thời và việc đóng file khi client hủy request. Không được đọc toàn bộ archive vài GB vào RAM.

Đây là giao thức HTTP chuẩn, có thể triển khai bằng Python stdlib. <Cite ref="turn224355search2"/>

**Hợp đồng offline:** Toàn bộ MapLibre JS, CSS, worker, font, glyph, sprite, style JSON và PMTiles phải đến từ localhost. Không được âm thầm tải CDN khi offline pack thiếu hoặc lỗi.

---

## 3. Terrain/3D: làm đúng dữ liệu, không chỉ nghiêng bản đồ

<grid columns={2} gap={3}>
  <grid-item>
    <AsyncImage query="MapLibre GL JS 3D OpenStreetMap buildings fill extrusion urban city map" aspectRatio="5:3" width="100%"/>
    **3D Buildings**

    <text color="secondary" size="sm">Dựng khối nhà bằng polygon và chiều cao từ OSM vector tiles.</text>
  </grid-item>
  <grid-item>
    <AsyncImage query="3D shaded relief digital elevation model terrain topographic map mountains maplibre" aspectRatio="5:3" width="100%"/>
    **3D Terrain**

    <text color="secondary" size="sm">Địa hình có độ cao thực, không phải hiệu ứng camera pitch.</text>
  </grid-item>
</grid>

### 3.1. Công trình 3D

**Nguồn dữ liệu được chọn: OSM building layer trong PMTiles.**

OpenMapTiles sử dụng các thuộc tính `render_height`, `render_min_height`; MapLibre hỗ trợ dựng nhà với `fill-extrusion`. Đây cũng là cách dùng trong ví dụ chính thức với OpenFreeMap. <Cite ref="turn224355search1"/>

Triển khai từ Q3, giới hạn theo zoom và thiết bị. Nếu chỉ có `building:levels`, chiều cao quy đổi là **ước tính**, không được trình bày là số đo thực tế. Nhà thiếu dữ liệu chiều cao không thể hiển thị chính xác như mô hình 3D đô thị chuyên dụng.

### 3.2. Terrain offline

Không thêm `mapbox-dem` như một URL online mặc định.

Chọn quy trình:

`SRTM/AW3D30 → chuẩn hóa DEM → encode Terrain-RGB → raster tiles cục bộ → MapLibre raster-dem`.

Ví dụ cấu hình runtime:

```javascript
map.addSource('vietgeo-dem', {
  type: 'raster-dem',
  tiles: ['/tiles/dem/{z}/{x}/{y}.png'],
  tileSize: 256,
  encoding: 'mapbox',
  maxzoom: 12
});

map.setTerrain({
  source: 'vietgeo-dem',
  exaggeration: 1
});
```

Đoạn này yêu cầu các PNG thật sự được mã hóa theo Mapbox Terrain-RGB, có tile endpoint cục bộ tương ứng. Không thể lấy PNG hillshade thông thường rồi khai báo `raster-dem`.

MapLibre hỗ trợ cả hillshade và 3D terrain từ DEM. <Cite refs={["turn232812search2","turn232812search7"]}/>

**Không đóng gói DEM độ phân giải cao toàn quốc trong gói mặc định.** Chỉ tải pack địa hình ở khu vực người dùng chọn. Điều này giảm đáng kể dung lượng lưu trữ và chi phí tạo dữ liệu.

---

## 4. Tìm kiếm và định tuyến: ưu tiên tính hữu ích trước 3D

### 4.1. Geocoding: giữ FTS5, không triển khai Nominatim

Mã `db.py` hiện đã index chuỗi kết hợp tên địa điểm, địa chỉ, tỉnh và danh mục, đồng thời hỗ trợ tìm không dấu. Vấn đề chính không phải thiếu search engine mà là thiếu dữ liệu địa chỉ có cấu trúc.

Tôi chọn mở rộng SQLite bằng các bảng `addresses`, `streets`, `admin_units` và `aliases`, có trường mã đơn vị hành chính, tọa độ và provenance riêng. Không đưa mọi bản ghi đường phố vào bảng `places`.

Đường tìm kiếm duy nhất:

`Query tiếng Việt → normalize → parse thành phần địa chỉ → FTS5 candidate retrieval → ranking theo loại khớp, vị trí và độ đầy đủ địa chỉ → autocomplete`.

Overpass chỉ phục vụ chức năng nhập/cập nhật dữ liệu khi online, **không dùng làm fallback cho từng lượt gõ tìm kiếm**.

Nominatim không phù hợp với mục tiêu runtime nhẹ vì yêu cầu PostgreSQL và quy trình import riêng; tài liệu chính thức cho thấy việc vận hành dữ liệu OSM quy mô lớn có yêu cầu tài nguyên đáng kể. <Cite ref="turn232812search1"/>

Một lưu ý quan trọng: 3.321 xã/phường hiện mới là dữ liệu tên và điểm đại diện, không phải polygon ranh giới pháp lý. Reverse geocoding muốn trả chính xác xã/phường theo tọa độ sẽ cần dữ liệu polygon hợp lệ hoặc một nguồn xác minh tương đương.

### 4.2. Routing: chọn Valhalla

Valhalla có profile ô tô, đi bộ, xe đạp và một số loại phương tiện hai bánh. Nó phù hợp với bài toán đa phương tiện hơn một triển khai OSRM chỉ có car profile trong phạm vi hiện tại. <Cite ref="turn613352search3"/>

Kiến trúc triển khai:

- Python VietGeo vẫn chạy độc lập, không bắt buộc Docker.
- Valhalla nằm trong sidecar container, tạo routing graph từ OSM PBF.
- Python cung cấp `/api/route`, chuyển tiếp yêu cầu đến service nội bộ đã cấu hình cố định.
- Khi Valhalla chưa được cài hoặc graph chưa sẵn sàng, UI thông báo rõ "Định tuyến offline chưa được cài đặt".

Routing graph và PMTiles nên được tạo từ cùng một snapshot OSM để giảm khác biệt dữ liệu đường sá. Docker Valhalla có cơ chế tạo và sử dụng tile routing cục bộ. <Cite ref="turn232812search0"/>

Dữ liệu OSM không bảo đảm đầy đủ mọi quy định giao thông tại Việt Nam. Đặc biệt, không mặc định coi profile ô tô là profile xe máy. Cần kiểm tra đường cấm, cầu, đường một chiều, giới hạn phương tiện, turn restrictions và chất lượng hướng dẫn tiếng Việt trước khi mở chế độ tương ứng.

**Traffic realtime không nằm trong roadmap này.** Routing offline vẫn có thể tính tuyến đường, khoảng cách, thời gian ước tính theo tốc độ mô hình; không thể khẳng định phản ánh tắc đường hiện tại.

---

## 5. Roadmap một phương án duy nhất — Q1 / Q2 / Q3

Định nghĩa Q1–Q3 là ba quý triển khai liên tiếp, dự kiến từ đầu năm 2027. Các mục dưới đây là phạm vi và gate, không phải cam kết lịch hoàn thành khi chưa ước lượng nhân lực.

<table>
  <table-row>
    <table-cell width="33%">
      <box gap={2}>
        <title size="lg">Q1</title>
        <text color="secondary" weight="medium" size="xs">Offline Foundation</text>
        **Mục tiêu:** Bản đồ Việt Nam chạy được khi cắt mạng.

        - Self-host MapLibre, worker, CSS
        - Planetiler → PMTiles
        - HTTP Range chuẩn
        - Style, glyph, sprite local
        - Offline package manifest
        - Import POI thật
        - Benchmark bbox D-005
        - Security + regression gates

        <divider color="subtle"/>
        **Exit gate:** Internet bị chặn hoàn toàn, vẫn khởi động, kéo/zoom, tìm kiếm và mở POI trong phạm vi dữ liệu đã cài.
      </box>
    </table-cell>
    <table-cell width="33%">
      <box gap={2}>
        <title size="lg">Q2</title>
        <text color="secondary" weight="medium" size="xs">Search + Routing</text>
        **Mục tiêu:** Trải nghiệm sử dụng hằng ngày.

        - Vietnamese autocomplete
        - Street/address index
        - Alias hành chính
        - Search ranking v2
        - Reverse geocoding cục bộ
        - Valhalla sidecar
        - Route polyline + ETA
        - Route QA theo phương tiện

        <divider color="subtle"/>
        **Exit gate:** Tìm địa chỉ và tìm đường trên dữ liệu offline; không phát sinh gọi dịch vụ geocoding/routing công khai.
      </box>
    </table-cell>
    <table-cell width="33%">
      <box gap={2}>
        <title size="lg">Q3</title>
        <text color="secondary" weight="medium" size="xs">Terrain + 3D</text>
        **Mục tiêu:** Hiển thị không gian nâng cao.

        - DEM offline regional pack
        - Hillshade + terrain
        - 3D buildings OSM
        - Performance-based LOD
        - Quản lý gói bản đồ
        - Incremental dataset updates
        - Data provenance/rollback
        - Polish giao diện và accessibility

        <divider color="subtle"/>
        **Exit gate:** 3D hoạt động trên thiết bị hỗ trợ, có graceful fallback về 2D và không làm ảnh hưởng dữ liệu cá nhân.
      </box>
    </table-cell>
  </table-row>
</table>

### Chính sách phân phối dữ liệu

Chọn **hai cấp dữ liệu trong cùng một sản phẩm**, không tách thành hai ứng dụng:

- **Starter pack:** nền vector toàn quốc ở zoom thấp/trung bình, bộ hành chính và dữ liệu POI nền tảng đã được kiểm chứng. Phải sử dụng được hoàn toàn offline ngay sau khi cài đầy đủ gói này.
- **Regional detail packs:** zoom cao, tòa nhà, DEM và routing graph theo vùng. Người dùng cài trước khi đi offline.

Nếu muốn zoom cao trên toàn bộ Việt Nam mà không có mạng, phải cài đủ các gói tương ứng. Không nên tuyên bố "full nationwide offline" nếu chỉ đóng gói mức zoom thấp.

Dung lượng thực tế phải được đo từ artifact đã tạo. Vector toàn quốc, routing graph và DEM độ phân giải cao có thể đưa tổng dung lượng lên mức nhiều GB; không nên đưa con số chính xác khi chưa build dữ liệu.

---

## 6. Performance — quyết định D-005

Baseline được cung cấp:

<Chart content={{"chartType":"bar","meta":{"title":"SQL benchmark — 50.000 POI tổng hợp","description":"Đơn vị ms. Số liệu của Hermes, chưa phải end-to-end browser latency."},"xKey":"query","series":[{"dataKey":"ms","label":"Độ trễ","valueSuffix":" ms"}],"yAxisMin":0,"data":[{"query":"FTS","ms":1.4},{"query":"BBox + sort","ms":93.5},{"query":"Near + sort","ms":36.8},{"query":"Wards JSON","ms":2.4}]}}/>

BBox là truy vấn chậm nhất trong bốn phép đo này. Theo brief, có khoảng 33.000 hàng tham gia bước sort. Điều đó khiến việc kiểm tra D-005 có cơ sở, nhưng vẫn cần tách chi phí RTree join, materialization và sort bằng execution plan cùng benchmark A/B.

Một điểm dễ bỏ sót: trong `app.js`, mỗi khi di chuyển bản đồ, client đợi khoảng 280 ms rồi truy vấn lại tối đa 400 POI và cập nhật GeoJSON source. Vì thế độ trễ người dùng nhìn thấy không bằng riêng thời gian SQL.

### Thứ tự tối ưu hiệu năng

1. **Network-independent basemap:** loại bỏ độ trễ CDN và thất bại khi mất kết nối.
2. **Đo browser end-to-end:** `style.load`, tile fetch/decode, frame time, thời gian API và `setData()`.
3. **D-005:** giữ nguyên tính đúng đắn của `ORDER BY id DESC`, thử các execution plan khác nhau trên bbox nhỏ, lớn và phân trang.
4. **Điều chỉnh viewport refresh:** tránh request dư thừa, payload lớn và cập nhật lại toàn bộ source khi không cần.
5. **LOD cho 3D:** chỉ render lớp công trình/terrain khi zoom và hiệu năng cho phép.

Không loại bỏ thứ tự kết quả chỉ để tăng benchmark.

### Performance acceptance targets

Các mức dưới đây là **mục tiêu đề xuất**, không phải kết quả đã đạt.

| Gate | Mục tiêu |
|---|---|
| FTS autocomplete | p95 ≤ 50 ms server-side |
| BBox query | p95 ≤ 100 ms tại 100k POI đại diện |
| POI API | p95 ≤ 150 ms với viewport phổ biến |
| Tương tác bản đồ 2D | Ưu tiên ≥ 50 FPS trên máy benchmark |
| UI search | Không hiển thị kết quả cũ sau request mới |
| Offline network | 0 request tới origin bên ngoài |
| PMTiles Range | 206/416/HEAD và checksum PASS |
| 3D | Graceful fallback nếu GPU hoặc dữ liệu không đủ |

Phải đo cold/warm cache riêng, và kiểm thử cả máy có GPU tích hợp, không chỉ workstation mạnh.

---

## 7. Trade-off offline-first đã chấp nhận

| Khía cạnh | Được | Đánh đổi |
|---|---|---|
| Vector offline | Style tùy biến, không lệ thuộc CDN | Phải build, lưu và cập nhật tiles |
| Search local | Nhanh, riêng tư, không có phí API theo lượt | Phụ thuộc độ đầy đủ dữ liệu nhập |
| Routing offline | Không cần mạng để tính tuyến | Graph tốn dung lượng, cần cập nhật đường |
| 3D buildings | Trải nghiệm thị giác phong phú | OSM thiếu chiều cao nhiều công trình |
| Terrain | Hiển thị địa hình thật | DEM nặng, cần xử lý và đóng gói |
| Không traffic cloud | Không phát sinh phụ thuộc dịch vụ realtime | Không biết ùn tắc đang diễn ra |

**Nguyên tắc bất biến:** phần mềm và dữ liệu phải được tách riêng. Có thể cập nhật pack bản đồ mà không thay đổi chương trình; cập nhật phải kiểm tra hash, schema, metadata, giấy phép, lưu snapshot cũ và cho phép rollback. Dữ liệu người dùng trong SQLite không được bị ghi đè khi thay thế basemap.

---

## 8. Phán quyết dành cho Hermes Lead Orchestrator

<box border radius="lg" padding={3} gap={2}>
  <row align="center" justify="between">
    **VGN-MAP-001**
    <badge>GO — Planning</badge>
  </row>
  **Task duy nhất giao Devin CLI tiếp theo: Offline Vector Foundation**

  Phạm vi đầu tiên: tự host toàn bộ MapLibre assets, tích hợp PMTiles protocol, tạo HTTP Range handler và chạy một archive thử nghiệm nhỏ được phép phân phối. Chưa triển khai Valhalla, Nominatim hoặc terrain.

  **Acceptance bắt buộc:**
  - Khởi động bằng Python stdlib, không cài pip runtime.
  - Map render thực tế qua localhost với Internet bị chặn.
  - `206`, `416`, `HEAD`, CSP và path allowlist PASS.
  - Không có external network request khi offline.
  - Không regression POI, CRUD, FTS, clustering và style switching.
  - Có benchmark, logs, nguồn dữ liệu, SHA-256 và browser evidence để Hermes tự kiểm chứng.

  Chỉ sau khi gate này đạt mới chuyển sang build PMTiles Việt Nam thực và import POI. Không merge cả Q1–Q3 thành một PR.
</box>

**Quyết định tổng thể:** VietGeo nên trở thành một **Google-Maps-like offline navigation and discovery tool**, không phải một bản sao Google Maps cloud. Lợi thế cạnh tranh nên tập trung vào bản đồ Việt Nam độc lập, dữ liệu có thể kiểm chứng, tìm kiếm tiếng Việt, chạy không mạng và người dùng sở hữu dữ liệu của mình. 3D là nâng cấp sau cùng; bản đồ offline có dữ liệu thật và tìm đường hữu dụng mới là giá trị cốt lõi.