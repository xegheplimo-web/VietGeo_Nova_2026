# Card P0-B — mypy 9 lỗi + xoá BUILD_MANIFEST.json stale

## TASK
1. Sửa 9 lỗi mypy trong `vietgeo/` và thêm job `mypy` vào CI để chặn regression.
2. Xoá `BUILD_MANIFEST.json` (đã stale, 0 dependency).

## GOAL
Type-safety thật sự enforce được; bỏ artifact sai lệch đang gây nhầm lẫn về trạng thái repo.

## OWNERSHIP SCOPE (create/modify ONLY these paths)
- `vietgeo/db.py`
- `vietgeo/osm.py`
- `.github/workflows/ci.yml`
- `pyproject.toml`
- `BUILD_MANIFEST.json` (xoá)

## READ-ONLY INPUTS (đọc được, KHÔNG sửa)
`vietgeo/server.py`, `tests/`, `tools/`, `uv.lock`, `docs/`, `web/`, `Dockerfile`, `compose.yaml`

## KNOWN EVIDENCE (đã verify)
- `uvx --with mypy mypy vietgeo tools` → **9 lỗi**:
  - `db.py:73` arg-type `str | PathLike[str] | None`
  - `db.py:113` call-overload `MutableMapping.update`
  - `db.py:150` return-value `tuple[int | None, bool]` vs `tuple[int, bool]`
  - `db.py:196,199,211,228` arg-type `append` `str` vs `float`
  - `osm.py:72` return-value `Any | Collection[str]` vs `str`
- mypy **chưa** có trong CI (chỉ lint + test).
- `BUILD_MANIFEST.json`: 9/30 hash lệch HEAD, 8 file tracked thiếu, **0 dependency** (grep toàn repo = chỉ chính file đó + brief của audit).

## DELIVERABLES
1. `vietgeo/db.py`, `vietgeo/osm.py`: sửa 9 lỗi mypy (KHÔNG đổi semantics — chỉ sửa type/khai báo).
2. `pyproject.toml`: khai báo `[tool.mypy]` nếu cần (đã có sẵn phần này — kiểm tra, đừng trùng).
3. `.github/workflows/ci.yml`: thêm job `Typecheck` chạy `mypy vietgeo tools`, chạy trên ubuntu-latest, Python 3.10–3.13 hoặc 1 matrix phù hợp; dùng `uvx --with mypy mypy`.
4. `BUILD_MANIFEST.json`: xoá.
5. Báo cáo cuối: paste output thật của `mypy` (phải = 0 error) + job mới trong ci.yml.

## ACCEPTANCE CRITERIA
- `uvx --with mypy mypy vietgeo tools` → **no issues found in 3 source files** (paste nguyên output).
- `python -m unittest discover -s tests` → **all pass** (paste số liệu).
- `uvx ruff@0.17.2 check . && uvx ruff@0.17.2 format --check .` → **All checks passed**.
- `BUILD_MANIFEST.json` không còn tồn tại trong cây làm việc.
- Job mới trong `ci.yml` hợp lệ YAML (verify bằng `uvx --with pyyaml python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml'))"`).
- **KHÔNG** đổi hành vi runtime của `db.py`/`osm.py` (chỉ type).

## VERIFY COMMANDS
```
uvx --with mypy mypy vietgeo tools
python -m unittest discover -s tests -v
uvx ruff@0.17.2 check .
uvx ruff@0.17.2 format --check .
```

## CONSTRAINTS
- **KHÔNG** tạo/ghi/sửa file trong `.devin/` (ForceAsk → chết phiên).
- **KHÔNG** sửa/xoá file nào ngoài OWNERSHIP SCOPE (kể cả "dọn dẹp").
- **KHÔNG** commit / push (Hermes sở hữu git).
- **KHÔNG** thêm dependency runtime mới (mypy là dev-only, chạy qua `uvx`).
- **KHÔNG** thêm `# type: ignore` rỗng để gate xanh — sửa type thật; nếu bắt buộc phải suppress thì kèm comment giải thích ngắn.
- Sau khi sửa file: `sed -i 's/\r$//' <file>` rồi kiểm `python -c "print(open(p,'rb').read().count(b'\r'))"` (phải = 0).

## STOP CONDITIONS
- Nếu sửa type đổi hành vi runtime → DỪNG, báo cáo (đừng "sửa" bằng cách nới type thành `Any`).
- Nếu job CI mới làm matrix test đỏ vì lý do không liên quan → DỪNG, báo cáo output thật.
