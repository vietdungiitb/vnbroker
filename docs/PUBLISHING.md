# Phát hành vnbroker lên PyPI

Trạng thái hiện tại: **chưa có bản nào trên PyPI.** Tên `vnbroker` còn trống
(`https://pypi.org/simple/vnbroker/` → 404).

Repo: **private**. Vì vậy dùng **API token**, không dùng Trusted Publishing
(OIDC chỉ dùng được khi repo public).

---

## 1. Cấu hình một lần

### 1.1 Tạo API token

- TestPyPI: https://test.pypi.org/manage/account/token/ — scope *Entire account*
  (bản đầu tiên chưa có project để giới hạn scope).
- PyPI: https://pypi.org/manage/account/token/ — sau lần phát hành đầu, tạo token
  mới giới hạn theo project `vnbroker` rồi thu hồi token cũ.

### 1.2 Thêm secret vào repo

```bash
gh secret set TESTPYPI_API_TOKEN --repo vietdungiitb/vnbroker
gh secret set PYPI_API_TOKEN     --repo vietdungiitb/vnbroker
```

Workflow sẽ báo lỗi rõ ràng nếu thiếu secret, thay vì thất bại khó hiểu.

### 1.3 (Tuỳ chọn) tạo environment để chặn publish ngoài ý muốn

`publish.yml` tham chiếu environment `pypi` / `testpypi`. Nếu chưa tạo, GitHub
dùng environment rỗng và workflow vẫn chạy. Muốn thêm người duyệt tay:

GitHub → Settings → Environments → New environment → `pypi` → Required reviewers.

---

## 2. Thử trên TestPyPI trước (bắt buộc với lần đầu)

Actions → **Publish to PyPI** → *Run workflow*:

- `confirm_version`: gõ đúng version trong `pyproject.toml` (ví dụ `3.5.0`)
- `target`: `testpypi`

Workflow sẽ: chạy `pytest tests/unit tests/contract` → `python -m build` →
`check_dist_contents.py` → `twine check` → upload lên TestPyPI.

Kiểm tra kết quả cài được thật:

```bash
python -m venv /tmp/probe && . /tmp/probe/bin/activate   # Windows: /tmp/probe/Scripts/activate
pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ vnbroker
python -c "import vnbroker, importlib.util as u; print(vnbroker.__file__); print('tests shadow:', u.find_spec('tests') is not None)"
```

> TestPyPI không có dependency, nên cần `--extra-index-url https://pypi.org/simple/`.
> `tests shadow` phải in **False** — đó là điều cổng `check_dist_contents.py` bảo vệ.

---

## 3. Phát hành thật

1. Merge `dev` → `main`, CI trên `main` phải **xanh** (xem mục 5).
2. Tag annotated + GitHub Release:

```bash
git checkout main && git pull
git tag -a v3.5.0 -m "vnbroker v3.5.0"
git push origin v3.5.0
gh release create v3.5.0 --title "vnbroker v3.5.0" --notes-file <(sed -n '/## \[3.5.0\]/,/^## \[/p' CHANGELOG.md)
```

3. Release ở trạng thái *published* → `publish.yml` chạy và đẩy lên PyPI.

Workflow **chặn** nếu tag không khớp version trong `pyproject.toml`
(`tag v3.5.0` ↔ `version = "3.5.0"`), nên không thể phát hành sai nhãn.

---

## 4. Các cổng đã có trong `publish.yml`

| Cổng | Kiểm gì | Vì sao cần |
|---|---|---|
| Tag ↔ version | `vX.Y.Z` khớp `pyproject.toml` | artifact không bị gắn sai nhãn |
| `pytest tests/unit tests/contract` | suite thật trên đúng commit phát hành | không phát hành code đỏ |
| `scripts/check_dist_contents.py` | wheel/sdist chỉ chứa `vnbroker` (+ `tests`, `scripts` ở sdist) | `twine check` **không** kiểm danh sách file |
| `twine check dist/*` | metadata + README render | lỗi metadata chặn upload |
| Xác nhận version khi chạy tay | gõ đúng version | tránh bấm nhầm |

---

## 5. Việc còn lại trước khi phát hành

- [ ] **CI trên `main` phải xanh.** Từ 2026-10-03 mọi run trên `main` đều
      `failure` với `steps: 0`, `runner_name: ""`, log `BlobNotFound` — chưa xác
      định được là lỗi hạ tầng hay lỗi code. Xem bằng `gh run list`.
- [ ] `build` job trong `test.yml` đang bị `skipped` (needs `[test, code-quality]`)
      và `python -m build` / `twine check` ở đó là `continue-on-error: true`,
      nên packaging **không** được kiểm ở đó — `publish.yml` mới là cổng thật.
- [ ] Bàn giao sạch: `git status` còn 18 file modified + 4 untracked; `dev` ahead 2.
- [ ] Thêm badge PyPI vào `README.md` sau khi phát hành lần đầu.

---

## 6. Vì sao repo private vẫn publish được

PyPI không đọc repo GitHub. Trusted Publishing (OIDC) cần GitHub là *identity
provider* và PyPI đối chiếu repo/tổ chức — nhưng điều kiện repo phải public
chưa được xác minh trong tài liệu đã đọc. API token không có ràng buộc đó.

Muốn chuyển sang OIDC sau này: đưa repo lên public → PyPI → Publishing →
*Add a new pending publisher* (owner `vietdungiitb`, repo `vnbroker`, workflow
`publish.yml`, environment `pypi`) → xoá secret và bỏ `password:` trong workflow.
