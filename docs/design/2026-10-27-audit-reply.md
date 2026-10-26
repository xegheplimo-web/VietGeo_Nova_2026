# VietGeo Nova 2026 — Phán quyết kiến trúc và release v1.0.0

<badge color="warning">HOLD — chưa đủ điều kiện tuyên bố v1.0.0 hoàn chỉnh</badge>

**Kết luận:** VietGeo Nova có nền tảng kỹ thuật khá tốt cho một ứng dụng bản đồ *local-first*, nhưng chưa thể xác nhận là bản phát hành hoàn chỉnh, ổn định và an toàn chỉ dựa vào CI xanh 11/11.

Tôi đã đối chiếu thêm mã nguồn công khai trên GitHub, gồm `server.py`, `db.py`, `app.js`, `index.html`, `Dockerfile` và `BUILD_MANIFEST.json`. Những điểm quan trọng nhất:

- **CSP:** cần triển khai trước release; không cần nonce nếu giữ cấu trúc JavaScript hiện tại.
- **BBox:** chưa có bằng chứng cho rằng `ORDER BY` là nguyên nhân chủ yếu của 90,8 ms. Không nên sửa thuật toán khi chưa có query-plan và benchmark so sánh.
- **Manifest:** chọn **Option B — xóa `BUILD_MANIFEST.json`** khỏi source tree; không tái tạo một cơ chế kiểm tra hash tự tham chiếu.
- **Coverage:** 64% chưa đủ cơ sở để tự tin với các nhánh lỗi quan trọng, nhất là importer và HTTP server.
- **Dữ liệu:** 0 POI là vấn đề lớn hơn nhiều so với 90 ms truy vấn. Nếu quảng bá đây là bản đồ có đầy đủ địa điểm/doanh nghiệp Việt Nam, v1.0.0 hiện chưa đạt yêu cầu.

Một điểm bổ sung đặc biệt quan trọng: `Dockerfile` chỉ đưa `provinces_34.json` vào image, trong khi API xã/phường phụ thuộc `wards_3321.json`. Ngoài ra, mã `_host_allowed()` hiện chỉ chấp nhận Host thuộc `localhost`, `127.0.0.1`, `::1`, kể cả khi server bind `0.0.0.0`. Điều này có thể làm truy cập Docker qua IP máy chủ bị trả về 403. <Cite refs={["turn228997view2","turn553318view1"]}/>

Đây là hai vấn đề triển khai thực tế cần kiểm thử trước khi gắn nhãn production-ready.

## 1. CSP — Chọn A, nhưng không dùng nonce trong kiến trúc hiện tại

### 1.1. Điều chỉnh một giả định quan trọng

Trong `web/index.html` của repository, mã hiện tại là:

```html
<script type="module" src="/app.js"></script>
```

Đây là **external module script**, không phải inline script.

Ngoài ra, `web/app.js` tải MapLibre bằng dynamic import:

```javascript
state.lib = await import(
  'https://unpkg.com/maplibre-gl@6.15.0/dist/maplibre-gl.mjs'
);
```

Do đó, không có lý do kỹ thuật để tạo nonce theo từng request cho chính hai đoạn này. Nonce phù hợp khi cần cấp quyền cho các thẻ script cụ thể, đặc biệt là inline script. Với cấu trúc hiện tại, cho phép nguồn script được kiểm soát là đơn giản hơn. <Cite refs={["turn672200view1","turn370718view0","turn918137search4"]}/>

### 1.2. CSP khả dụng cho VietGeo Nova

Tôi đề xuất baseline thực thi sau, phù hợp với mô hình CDN hiện tại.

<CodeBlock language="python" editable>
CSP = "; ".join((
    "default-src 'self'",
    "script-src 'self' https://unpkg.com",
    "style-src 'self' https://unpkg.com 'unsafe-inline'",
    "img-src 'self' data: blob: "
        "https://tiles.openfreemap.org "
        "https://assets.openfreemap.com",
    "connect-src 'self' "
        "https://unpkg.com "
        "https://tiles.openfreemap.org "
        "https://assets.openfreemap.com",
    "font-src 'self' data: "
        "https://tiles.openfreemap.org "
        "https://assets.openfreemap.com",
    "worker-src 'self' blob:",
    "object-src 'none'",
    "base-uri 'none'",
    "frame-ancestors 'none'",
    "form-action 'self'",
))
</CodeBlock>

Đây là **baseline CSP có hiệu lực**, chưa phải chính sách CSP nghiêm ngặt nhất có thể. Hai phần nới quyền có chủ đích là CDN cho JavaScript và `unsafe-inline` cho CSS.

| Directive | Lý do |
|---|---|
| `script-src` | JavaScript nội bộ và MapLibre ESM từ unpkg |
| `style-src` | CSS ứng dụng, CSS CDN và tương thích inline styling |
| `img-src` | Sprite, hình ảnh và Blob/Data URL |
| `connect-src` | API nội bộ, style JSON, vector tiles, glyphs và tài nguyên được fetch |
| `font-src` | Dự phòng tài nguyên font của bản đồ |
| `worker-src` | Worker tạo qua Blob URL của MapLibre v6 |
| `object-src` | Chặn nội dung nhúng kiểu object |
| `frame-ancestors` | Ngăn ứng dụng bị nhúng vào frame khác |

Tài liệu MapLibre v6 xác nhận cách tải ESM qua CDN có thể sử dụng Blob worker. Vì vậy `worker-src 'self' blob:` là lựa chọn tương thích. Nếu self-host worker ở cùng origin, có thể bỏ `blob:`. <Cite refs={["turn918137search3","turn918137search0"]}/>

Lưu ý: OpenFreeMap có cả hạ tầng `tiles.openfreemap.org` và `assets.openfreemap.com`. Hai host được đưa vào baseline để bao phủ tài nguyên bản đồ, nhưng cần xác nhận chính xác danh sách origin của cả bốn style bằng Chrome Network trước khi khóa chính sách. <Cite refs={["turn918137search2","turn782160search3"]}/>

### 1.3. Cách tích hợp vào HTTP server

Có thể thêm phương thức sau vào `Handler` hiện tại:

<CodeBlock language="python" editable>
def end_headers(self):
    self.send_header(
        "Content-Security-Policy",
        CSP,
    )
    super().end_headers()
</CodeBlock>

Cần khai báo `CSP` tại module scope như ví dụ trên.

Điểm quan trọng: không chỉ thêm CSP trong `_send()`. Phương thức đó đang phục vụ phản hồi API, trong khi trang HTML và tài nguyên tĩnh đi qua `SimpleHTTPRequestHandler`. Override `end_headers()` sẽ áp dụng CSP cả cho phản hồi trang HTML. Cần kiểm tra để tránh ghi header trùng khi bổ sung các security header khác.

**Phương án tôi khuyến nghị cho bản phát hành ổn định hơn:** self-host đúng phiên bản MapLibre JavaScript, CSS và worker thay vì tải mã thực thi từ CDN. Khi đó, có thể thu hẹp `script-src` về `'self'`, `worker-src` về `'self'`, loại bỏ phụ thuộc CDN cho code và tăng tính tái lập build.

Việc này quan trọng hơn nonce/hash nếu mục tiêu là giảm supply-chain risk.

Riêng `style-src 'unsafe-inline'` chỉ nên giữ sau khi test xác nhận MapLibre cần nó. Không bao giờ mở `unsafe-inline` cho `script-src` chỉ để sửa lỗi render.

**Gate CSP:** Chỉ bật enforce sau khi thử đủ bốn kiểu bản đồ, marker clustering, popup, form thêm/sửa địa điểm, Geolocation và tải sprite/glyph. Không được có CSP violation ngoài các trường hợp đã được đánh giá và chấp nhận.

---

## 2. BBox 90,8 ms — Chưa được phép quy kết cho ORDER BY

Mã hiện tại trong `db.py` thực hiện phép nối với RTree khi có bbox:

```sql
JOIN places_rtree r ON r.id = p.id
```

Sau đó sắp xếp:

```sql
ORDER BY p.id DESC
LIMIT ? OFFSET ?
```

Tuy nhiên, **90,8 ms không chứng minh phần lớn thời gian nằm ở sorting**. <Cite ref="turn328206view0"/>

SQLite có thể chọn hai chiến lược khác nhau: sử dụng RTree để lọc không gian trước rồi sort kết quả, hoặc duyệt bảng `places` theo thứ tự khóa chính và kiểm tra điều kiện RTree. Phương án được chọn phụ thuộc độ chọn lọc của bbox, thống kê bảng và SQL thực tế.

### Quy trình kiểm chứng

Chạy `EXPLAIN QUERY PLAN` với chính câu SQL và các tham số benchmark đã đo, đối chiếu khi có và không có `ORDER BY`.

Nếu xuất hiện:

```text
USE TEMP B-TREE FOR ORDER BY
```

thì SQLite có dùng bộ sắp xếp tạm. Tuy nhiên, execution plan chỉ xác nhận sự tồn tại của bước sort, chưa đo được tỷ trọng thời gian của nó. <Cite ref="turn672200search1"/>

<box border radius="lg" padding={3} gap={2}>
  <text weight="medium">Ma trận benchmark nên chạy</text>
  <table>
    <table-row><table-cell>Dataset</table-cell><table-cell>50k / 250k / 1M POI</table-cell></table-row>
    <table-row><table-cell>Viewport</table-cell><table-cell>Nhỏ / đô thị / toàn quốc</table-cell></table-row>
    <table-row><table-cell>Query</table-cell><table-cell>RTree + sort / RTree không sort / thử truy vấn đảo thứ tự</table-cell></table-row>
    <table-row><table-cell>Metrics</table-cell><table-cell>p50, p95, matched rows, query plan</table-cell></table-row>
    <table-row><table-cell>Kiểm soát</table-cell><table-cell>Cùng máy, dữ liệu, LIMIT/OFFSET và điều kiện cache</table-cell></table-row>
  </table>
</box>

### Đánh giá ba lựa chọn

**Option A — chưa chấp thuận triển khai trực tiếp.**

`id` đã là `INTEGER PRIMARY KEY`. Việc thêm index tổng hợp không tự động giải quyết phép nối RTree. Một composite index có thể hữu ích cho bộ lọc `category` hay `province`, nhưng phải chứng minh bằng query plan.

Việc đẩy `LIMIT` xuống trước toàn bộ điều kiện lọc cũng có thể làm sai kết quả.

**Option B — bác bỏ.**

`ROW_NUMBER()` không có lợi ích mặc định so với phép sort hiện tại. Window function vẫn phải xử lý tập dữ liệu phù hợp với điều kiện lọc và thứ tự yêu cầu.

**Option C — không chọn cho production.**

Bỏ sort có thể nhanh hơn nhưng thứ tự kết quả RTree không phải hợp đồng ổn định. Pagination và giao diện danh sách có thể trở nên không nhất quán.

**Phán quyết: YAGNI cho thay đổi thuật toán, nhưng không YAGNI cho việc đo đạc.** Giữ SQL hiện tại và tạo benchmark có thể chạy lại. Nếu p95 tăng vượt ngưỡng trải nghiệm đã định trên dữ liệu thực, mới tối ưu.

---

## 3. BUILD_MANIFEST.json — Chọn B, xóa khỏi repository

Tôi không chấp thuận Option A trong hình thức hiện tại.

Manifest đang mang ba vấn đề:

- Hash lỗi thời làm mất giá trị kiểm chứng.
- Danh sách không bao phủ đầy đủ các file tracked.
- Nếu `BUILD_MANIFEST.json` cũng phải chứa hash của chính nó thì xuất hiện bài toán tự tham chiếu, không thể xử lý bằng cách cập nhật hash thông thường.

Một manifest chỉ có ý nghĩa nếu xác định rõ đối tượng được bảo vệ, phạm vi bao phủ và cách xác minh độc lập.

Git commit, CI test và manifest SHA-256 phục vụ các mục đích khác nhau. Không nên nói CI xanh tự nó chứng thực toàn vẹn của mọi artifact được phân phối. Nhưng việc duy trì một file hash thủ công trong source tree cũng không giải quyết được bài toán provenance.

**Quyết định phù hợp:**

Xóa `BUILD_MANIFEST.json` khỏi repository sau khi kiểm tra không có script hoặc tài liệu nào phụ thuộc nó.

Nếu cần xác minh ZIP, Docker image hay release artifact, tạo checksums tại thời điểm release, nằm **bên ngoài artifact được băm**, rồi phát hành cùng provenance/attestation phù hợp.

Không tạo CI gate chỉ để giữ một manifest không mang lại giá trị vận hành.

---

## 4. Priority order và release gate

### Thứ tự triển khai chính thức

| Thứ tự | Công việc | Quyết định | Chặn v1.0.0? |
|---|---|---|---|
| 1 | CSP và kiểm thử tài nguyên bản đồ | A điều chỉnh, enforce | Có, nếu tuyên bố hardened/secure |
| 2 | Docker, Host allowlist, packaging xã/phường | Sửa và test end-to-end | Có, với deployment được hỗ trợ |
| 3 | Xử lý 8 lỗi mypy, bổ sung regression tests | Bắt buộc trước stable signoff | Có trong tiêu chuẩn stable đề xuất |
| 4 | Manifest lỗi thời | B — xóa | Dọn trước release |
| 5 | Coverage 64% | Tập trung P0 trước, tăng dần lên ≥85% | Chặn nếu chưa đủ test các luồng thiết yếu |
| 6 | Wards JSON parse 2,4 ms | Cache theo mtime nếu cần | Không |
| 7 | BBox 90,8 ms | Giữ, benchmark lại với dữ liệu thực | Không, nếu đáp ứng performance gate |

Đối với riêng bốn hạng mục trong brief, thứ tự là:

**P0-2 CSP → P0-1 Manifest → P0-3 Wards cache → P0-4 BBox.**

Trong đó chỉ CSP là security hardening cần ưu tiên trước lời tuyên bố *secure v1*. Manifest thuộc release hygiene, còn hai mục hiệu năng chưa đủ căn cứ nâng lên P0.

### Những gate thực sự còn thiếu

<box gap={3}>
  <row align="start" gap={2}>
    <icon name="shield-check" color="secondary" size="lg"/>
    <box flex="1" gap={1}>
      **Security gate**

      CSP enforce được test trên trình duyệt thật; mọi thao tác ghi an toàn theo deployment mode; khi mở truy cập qua mạng phải có xác thực bắt buộc và Host allowlist cấu hình tường minh.
    </box>
  </row>
  <divider color="subtle"/>
  <row align="start" gap={2}>
    <icon name="database" color="secondary" size="lg"/>
    <box flex="1" gap={1}>
      **Data integrity gate**

      Import OSM → tìm kiếm → cập nhật → xuất CSV/GeoJSON → khởi động lại → dữ liệu còn nguyên. Kiểm tra nhất quán bảng `places`, FTS5, RTree, provenance và chống ghi đè dữ liệu người dùng.
    </box>
  </row>
  <divider color="subtle"/>
  <row align="start" gap={2}>
    <icon name="container" color="secondary" size="lg"/>
    <box flex="1" gap={1}>
      **Deployment gate**

      Windows, Linux và Docker hoạt động với đúng hướng dẫn, dữ liệu được mount/lưu bền vững, Docker smoke không chỉ kiểm tra `/api/health` mà còn kiểm tra các chức năng thực tế.
    </box>
  </row>
  <divider color="subtle"/>
  <row align="start" gap={2}>
    <icon name="test-tube" color="secondary" size="lg"/>
    <box flex="1" gap={1}>
      **Quality gate**

      `ruff` sạch, `mypy` 0 lỗi, regression cho HTTP/OSM/import/CRUD/FTS/RTree đạt, coverage tăng theo rủi ro và không còn lỗi nghiêm trọng đã biết.
    </box>
  </row>
  <divider color="subtle"/>
  <row align="start" gap={2}>
    <icon name="gauge" color="secondary" size="lg"/>
    <box flex="1" gap={1}>
      **Performance gate**

      Đo p95 API và end-to-end trên dữ liệu POI đại diện, không chỉ synthetic 50k. Đặt ngưỡng được thống nhất trước khi chạy benchmark; không điều chỉnh ngưỡng sau khi xem kết quả để hợp thức hóa PASS.
    </box>
  </row>
</box>

### Hai phân biệt quan trọng

**Thứ nhất: wards re-parse không phải bottleneck đáng kể.** 2,4 ms với JSON 284 KB không đáng ưu tiên hơn các lỗi đúng-sai. Nếu cache, nên dùng snapshot bất biến có version hoặc mtime để tránh đọc file đang được đồng bộ dở và trả dữ liệu không nhất quán.

**Thứ hai: rate limiting phải gắn với threat model.** Mã `osm.py` đã có giới hạn toàn cục tối đa một yêu cầu Overpass mỗi 60 giây. Đây không phải rate limit chung cho các API ghi dữ liệu, nhưng cũng không thể nói tất cả write path hoàn toàn không có giới hạn. <Cite ref="turn206406view0"/>

Nếu ứng dụng tuyệt đối chỉ chạy trên loopback, chưa cần tạo hệ thống rate-limit phức tạp cho CRUD. Nếu cho phép LAN hoặc public bind thì cần authentication mặc định, giới hạn tài nguyên, rate limiting cho write/import và test lạm dụng trước release.

---

## 5. Quyết định cuối dành cho Hermes

<box border radius="lg" padding={3} gap={2}>
  <row align="center" justify="between">
    **Release decision — HEAD `c8a60f9`**
    <badge color="warning">HOLD</badge>
  </row>
  <divider color="subtle"/>
  <text color="secondary" size="xs">Phạm vi quyết định: đánh giá kiến trúc dựa trên local-recon được cung cấp và đối chiếu mã nguồn công khai. Chưa thay thế kiểm chứng runtime độc lập tại commit mới.</text>
  **Task Devin CLI duy nhất nên thực hiện ngay:**

  `VGN-SEC-001 — CSP enforcement + browser compatibility regression`

  Scope: tích hợp CSP vào static HTML responses, giữ script policy không có `unsafe-inline`, kiểm thử MapLibre worker, toàn bộ style OpenFreeMap, CSS/sprite/glyph, các luồng UI thiết yếu và thêm regression test vào CI.

  **Acceptance:** CSP được gửi trong HTML response; UI không mất chức năng; browser regression PASS; không có CSP violation chưa được giải quyết; `unittest`/`ruff`/CI không regression.

  Hermes làm technical owner, độc lập verify và quyết định merge. Không trộn tối ưu bbox, tái thiết kế DB hay sửa manifest vào cùng task.
</box>

**Về nhãn v1.0.0:** Nếu VietGeo Nova được định nghĩa là *nền tảng bản đồ cho phép tự nhập dữ liệu địa điểm*, cơ sở dữ liệu POI ban đầu rỗng có thể là thiết kế hợp lệ, miễn tài liệu nói rõ. Nhưng nếu sản phẩm được giới thiệu là *bản đồ Việt Nam hoàn chỉnh, có đầy đủ địa điểm, cửa hàng và doanh nghiệp*, tình trạng 0 POI là release blocker trực tiếp, bất kể CSP, coverage hay hiệu năng đã đạt.

Tôi khuyến nghị giữ **HOLD cho v1.0.0 stable**, hoàn thành hardening và kiểm thử triển khai trước, rồi đánh giá riêng data readiness. Không nên coi 11/11 CI thành công là giấy chứng nhận hoàn thiện sản phẩm.