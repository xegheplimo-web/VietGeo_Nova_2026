# Card P0-A — Security headers (CSP) + Docker host allowlist

## TASK
Hardening bảo mật HTTP layer của `vietgeo/server.py`:
1. Thêm `Content-Security-Policy` cho mọi response (qua override `end_headers()`).
2. Sửa host-allowlist khi server bind `0.0.0.0` trong container (`VIETGEO_CONTAINER=1`).

## GOAL
- XSS surface từ CDN (MapLibre unpkg) bị chặn bằng CSP.
- Docker deployment (compose, publish port) hoạt động thật — hiện tại bị 403 với mọi Host không phải loopback.

## OWNERSHIP SCOPE (create/modify ONLY these paths)
- `vietgeo/server.py`
- `tests/test_vietgeo.py`

## READ-ONLY INPUTS (đọc được, KHÔNG sửa)
`web/index.html`, `web/app.js`, `vietgeo/db.py`, `vietgeo/osm.py`, `Dockerfile`, `compose.yaml`, `.env.example`, `docs/design/2026-10-27-audit-brief.md`, `docs/design/2026-10-27-audit-reply.md`

## KNOWN EVIDENCE (đã verify, đừng đo lại từ đầu)
- `server.py` hiện có: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Cache-Control: no-store` trên `/api/*`.
- **Thiếu hoàn toàn `Content-Security-Policy`** (grep = 0 hit trong repo).
- `web/index.html`: `<script type="module" src="/app.js"></script>` (external, KHÔNG inline) → CSP không cần nonce.
- `web/app.js` dynamic `import()` từ `https://unpkg.com/maplibre-gl@...`; tile từ `https://tiles.openfreemap.org`.
- HTML được serve qua `SimpleHTTPRequestHandler` → phải override `end_headers()`, KHÔNG phải `_send()` (chỉ dùng cho `/api/*`).
- **`_host_allowed()` tại `server.py:120`**: chỉ chấp nhận `localhost`/`127.0.0.1`/`::1`, nếu không → 403.
- **Runtime-verify 2026-10-27:** bind `0.0.0.0:8799` + `VIETGEO_CONTAINER=1`, gửi `Host: 192.168.1.50:8799` → **HTTP 403** (loopback vẫn 200). → bug thật.

## DELIVERABLES
1. `vietgeo/server.py`: CSP header trên mọi response; host-allowlist mở khi `VIETGEO_CONTAINER=1`.
2. `tests/test_vietgeo.py`: test mới cho (a) CSP có trong response HTML, (b) CSP có trong response `/api/health`, (c) host loopback 200, (d) `VIETGEO_CONTAINER=1` + Host LAN không còn 403.
3. Báo cáo cuối: paste output thật (số test pass, curl response headers).

## ACCEPTANCE CRITERIA
- `curl -si http://127.0.0.1:<port>/` có dòng `Content-Security-Policy:` không rỗng.
- `curl -si http://127.0.0.1:<port>/api/health` có dòng `Content-Security-Policy:`.
- Test mô phỏng `VIETGEO_CONTAINER=1` + `Host: 10.0.0.5:<port>` → **KHÔNG 403**.
- CSP phải cho phép: `script-src 'self' https://unpkg.com`; `style-src 'self' 'unsafe-inline' https://unpkg.com`; `img-src 'self' data: blob: https://tiles.openfreemap.org`; `worker-src 'self' blob:`; `connect-src 'self' https://tiles.openfreemap.org https://overpass-api.de`; `default-src 'self'`.
- `python -m unittest discover -s tests` → **all pass** (paste số liệu).
- `uvx ruff@0.17.2 check . && uvx ruff@0.17.2 format --check .` → **All checks passed**.

## VERIFY COMMANDS
```
python -m unittest discover -s tests -v
uvx ruff@0.17.2 check .
uvx ruff@0.17.2 format --check .
uvx ruff@0.17.2 format .
node --check web/app.js
```

## CONSTRAINTS
- **KHÔNG** tạo/ghi/sửa file trong `.devin/` (ForceAsk → chết phiên). Nếu cần config toolchain, chỉ mô tả trong docs.
- **KHÔNG** sửa/xoá file nào ngoài OWNERSHIP SCOPE (kể cả "dọn dẹp" — mọi thay đổi ngoài scope bị revert và không được chấp nhận).
- **KHÔNG** commit / push (Hermes sở hữu git).
- **KHÔNG** thêm dependency mới.
- **KHÔNG** tắt test hay nới security check để gate xanh.
- Sau khi sửa file: chuẩn hoá line-ending `sed -i 's/\r$//' <file>` rồi kiểm `python -c "print(open(p,'rb').read().count(b'\r'))"` (phải = 0).
- Giữ nguyên hành vi đã verify của header cũ.

## STOP CONDITIONS
- Nếu CSP làm MapLibre không tải được trong browser thật → DỪNG, báo cáo evidence (không tự nới CSP ra vô nghĩa).
- Nếu test mới đỏ và nguyên nhân không rõ → DỪNG, báo cáo output thật.
