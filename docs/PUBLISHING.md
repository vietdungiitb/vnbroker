# Phát hành vnbroker lên PyPI

**Đã phát hành:** https://pypi.org/project/vnbroker/3.5.0/ (2026-10-07, thủ công qua `twine`).

Trạng thái:

| | |
|---|---|
| Release trên PyPI | `3.5.0` (1 release, 2 file) |
| Tên `vnbroker` | đã đăng ký, thuộc tài khoản `vietdungiitb` |
| Repo | **private** → dùng **API token**, không dùng Trusted Publishing (OIDC) |
| Workflow publish | `.github/workflows/publish.yml` — chưa chạy lần nào (CI đang bị chặn billing) |

> ⚠️ **PyPI không cho ghi đè version.** `3.5.0` đã tồn tại vĩnh viễn. Mọi lần
> publish tiếp theo phải là version mới (`3.5.1`, `3.6.0`, ...) — bump
> `pyproject.toml` trước, nếu không `publish.yml` sẽ đỏ ở bước upload dù mọi cổng
> xanh. Và PyPI **không xoá được** file đã upload, chỉ yank được.

---

## Cấu hình một lần (đã xong cho 3.5.0)

### 1.1 Tạo API token

- TestPyPI: https://test.pypi.org/manage/account/token/
- PyPI: https://pypi.org/manage/account/token/

Lần đầu chưa có project nên phải dùng scope *Entire account*. Sau khi đã có project
`vnbroker`, tạo token mới **giới hạn theo project** rồi thu hồi token cũ.

> Token TestPyPI và token PyPI **trông giống nhau** (đều bắt đầu `pypi-`) nhưng
> chỉ có giá trị ở index tương ứng. Dùng sai index cho ra `403 Forbidden` trần
> trụi — đây là nguyên nhân của lần upload hỏng đầu tiên (2026-10-07).

### 1.2 Thêm secret vào repo (cho `publish.yml`)

```bash
gh secret set TESTPYPI_API_TOKEN --repo vietdungiitb/vnbroker
gh secret set PYPI_API_TOKEN     --repo vietdungiitb/vnbroker
```

### 1.3 Điều kiện tài khoản

- **Email phải đã xác minh.** PyPI bắt buộc email verified để *Register a new
  project* và *Upload a new version or file*; thiếu thì lỗi là **403**.
- **2FA bắt buộc** để tạo token.

---

## Cách publish thủ công (đã dùng cho 3.5.0)

```bash
# 1. Build từ cây SẠCH, không phải cây làm việc có file rác
mkdir -p /tmp/rel && git archive HEAD | tar -x -C /tmp/rel && cd /tmp/rel
uv build --out-dir dist

# 2. Chạy cổng trước khi upload
python scripts/check_dist_contents.py dist/     # twine check KHÔNG kiểm file list
twine check dist/*

# 3. Upload — twine tự đặt username __token__, chỉ hỏi token
uvx twine upload --repository pypi dist/*

# hoặc dùng biến môi trường, tránh token lọt vào shell history:
read -rs TWINE_PASSWORD && export TWINE_USERNAME=__token__ TWINE_PASSWORD
uvx twine upload --repository pypi dist/*
```

Nếu gặp `403 Forbidden`, chạy lại với `--verbose` để lấy `{"message": ...}` thật.
⚠️ `--verbose` in cả header `Authorization` chứa token — **đừng dán toàn bộ output
đi đâu**.

## Cách publish qua GitHub

Actions → **Publish to PyPI** → *Run workflow*:

- `confirm_version`: gõ đúng version trong `pyproject.toml`
- `target`: `testpypi` hoặc `pypi`

Hoặc tạo GitHub Release `vX.Y.Z` → tự publish lên PyPI.

---

## Các cổng trong `publish.yml`

| Cổng | Kiểm gì | Vì sao cần |
|---|---|---|
| Tag ↔ version | `vX.Y.Z` khớp `pyproject.toml` | artifact không bị gắn sai nhãn |
| `pytest tests/unit tests/contract --maxfail=1` | suite thật trên đúng commit phát hành | không phát hành code đỏ |
| `scripts/check_dist_contents.py` | wheel/sdist chỉ chứa `vnbroker` (+ `tests`, `scripts` ở sdist) | `twine check` **không** kiểm danh sách file |
| `twine check dist/*` | metadata + README render | lỗi metadata chặn upload |
| Kiểm tra secret tồn tại | báo lỗi rõ ràng khi thiếu token | tránh thất bại khó hiểu |

---

## Việc còn lại

- [ ] **CI trên `main` phải xanh.** Từ 2026-10-03 mọi run đều `failure` với
      `steps: 0`, `runner_name: ""` — nguyên nhân lấy từ check-run annotations:
      *"The job was not started because recent account payments have failed or your
      spending limit needs to be increased."* Đây là **hết quota/billing GitHub
      Actions**, không phải lỗi code. Xử lý ở github.com/settings/billing.
- [ ] **Bump version trước lần publish kế tiếp** — `3.5.0` đã chiếm.
- [ ] Tạo token PyPI giới hạn theo project `vnbroker` và thu hồi token *Entire account*.
- [ ] Thêm badge PyPI vào `README.md` (đã thêm).

---

## Vì sao repo private vẫn publish được

PyPI không đọc repo GitHub. Trusted Publishing (OIDC) cần GitHub làm identity
provider; điều kiện repo phải public chưa được xác minh trong tài liệu. API token
không có ràng buộc đó.

Muốn chuyển sang OIDC sau này: đưa repo lên public → PyPI → Publishing →
*Add a new pending publisher* (owner `vietdungiitb`, repo `vnbroker`, workflow
`publish.yml`, environment `pypi`) → xoá secret và bỏ `password:` trong workflow.
