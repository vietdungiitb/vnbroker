"""
Khoa hành vi của cổng `scripts/check_tcbs_bodies.py` trong pytest.

Vì sao cần test cho **cổng**: một gate mà không ai test thì không biết nó có cắn không.
Test ở đây khoá 4 thứ:

  1. Cổng **thật sự** đọc payload bằng AST và tìm đủ 8 method write của TCBS.
  2. Baseline **đủ hạt** — thêm field sai mới vào method đã bị gắn cỏ vẫn phải báo lệch mới.
     (Đã bắt ngay khi chạy fail-trước: key chỉ gồm KIND+method thì lọt im lặng.)
  3. Heuristic `SUSPECT` không báo bừa (`requestId` ≠ `side`).
  4. Cổng exit 2 khi không verify được — không bao giờ exit 0 trong im lặng.

Ngoài ra khoá **hợp đồng tiền thật**: các field `required` mà spec nói rõ đang thiếu
trong payload hiện tại. Đây là bug đang tồn tại — test ghi lại để **không ai sửa code
làm chúng biến mất khỏi danh sách** mà không biết mình đang sửa cái gì.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[4]
SCRIPTS = REPO / "scripts"
GATE = SCRIPTS / "check_tcbs_bodies.py"
BASELINE = REPO / "docs" / "tcbs_body_baseline.json"

sys.path.insert(0, str(SCRIPTS))
import check_tcbs_bodies as gate  # noqa: E402


def _run(*args: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(GATE), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(REPO), shell=False,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


# ── 1. Cổng thật sự quét được payload ──────────────────────────────────────────


def test_gate_tim_thay_du_12_write_method() -> None:
    """
    Khoa **phu** cua cổng, khong phai con so "8".

    Vì sao 12: `money.py` va `condition_orders.py` viet `payload: dict = {...}`
    (**co annotation**) ⇒ gate bo sot 4 method do neu chi bat `ast.Assign`.
    Đã xảy ra: phu hiện 8/12 mà gate van bao xanh (audit round 3, major).

    ⚠ Khi them 1 write method moi, **sua con so nay** — va cung sua dong
    `docs/tcbs_body_baseline.json` bang `--write-baseline` roi xem `lech moi`.
    """
    rows = gate.collect_payloads()
    assert len(rows) == 12, f"ky vong 12 payload write, thuc te {len(rows)}"
    files = {w.split(":")[0] for w, *_ in rows}
    assert files == {
        "vnbroker\\broker\\tcbs\\derivative_orders.py",
        "vnbroker\\broker\\tcbs\\equity.py",
        "vnbroker\\broker\\tcbs\\money.py",
        "vnbroker\\broker\\tcbs\\condition_orders.py",
    }, f"thieu file nao khong duoc quet: {files}"


def test_gate_bat_duoc_kwarg_payload() -> None:
    """
    Khoa lỗ phủ thứ 2: `self._post(url, payload=payload)` — **kwarg**, khác
    `self._post(url, payload)`. Bỏ qua `node.keywords` thì method bi bỏ sót
    mà gate vẫn xanh (đã đo: 7 payload → 0 lệch → exit 0).
    """
    import inspect

    src = inspect.getsource(gate._gated_body_call)
    assert "keywords" in src, (
        "_gated_body_call khong xu ly `node.keywords` ⇒ bo sot payload truyen "
        "bang kwarg (`post(url, payload=payload)`)"
    )


def test_moi_payload_deu_biet_path_that() -> None:
    """Path phai la path that cua spec (dung chuan hoa de so sanh)."""
    rows = gate.collect_payloads()
    assert rows
    for _where, path, _fn, _payload in rows:
        assert path.startswith("/"), f"path khong phai path that: {path}"
        assert " " not in path, f"path co khoang trang: {path}"


def test_read_method_khong_bi_nham_nhapayload() -> None:
    """`get_positions` khong gui lenh ⇒ khong duoc co trong ket qua."""
    names = [fn for *_rest, fn, _p in
             [(w, p, f, pl) for w, p, f, pl in gate.collect_payloads()]]
    assert "get_positions" not in names
    assert not any(n.startswith("get_") for n in names)


# ── 2. Baseline du hat ────────────────────────────────────────────────────────


def test_baseline_co_ten_field_chu_khong_chi_ten_method() -> None:
    """
    Khoa L-I: baseline chi khoa theo `KIND + method` thi field sai moi lot qua.
    O day moi field bat buoc.
    """
    data = json.loads(BASELINE.read_text(encoding="utf-8"))
    keys = data["known_mismatches"]
    assert keys, "baseline rong"
    # moi key phai co >= 3 phan: KIND, file:Class.method, chi tiet field
    assert all(len(k.split()) >= 3 for k in keys), keys[:3]


def test_baseline_che_biet_het_lech_dang_co() -> None:
    """Xoa 1 dong baseline phai lam gate bat lai ngay."""
    spec = json.loads((REPO / "docs/references/openapi-v1.0.0.json").read_text(encoding="utf-8"))
    problems, count = gate.scan(spec)
    assert count > 0
    baseline = gate.load_baseline(BASELINE)
    active = [p for p in problems if not gate._in_baseline(p, baseline)]
    assert active == [], f"{len(active)} lech khong duoc baseline che:\n" + "\n".join(active[:5])


# ── 3. Heuristic SUSPECT khong bao bua ─────────────────────────────────────────


def test_suspect_chi_bat_dung_cap_roi() -> None:
    props = {"accountId", "subAccountId", "side", "symbol", "price", "volume",
             "orderType", "refId"}
    # `requestId` -> `refId` la nghi DUNG (spec goi truong idempotency la refId)
    assert gate._closest_spec_field("requestId", props) == "refId"
    # `side` qua ngan nen khong duoc nho voi `requestId`
    assert gate._closest_spec_field("side", props) != "requestId"
    # ten hoan toan la khong -> None (gate bao EXTRA, khong doan nghia)
    assert gate._closest_spec_field("zzz_bogus", props) is None


def test_suspect_khong_phai_nguon_su_hoi() -> None:
    """
    Heuristic CHI la goi y, khong phai ket luan. Hai truong hop doc **co chu dich**
    khong bat duoc, va test nay ghi lai de khong ai hua xoa:

      - `orderId` vs `orderNo`: phu trung ky tu 5/7 = 0.71 < 0.8 ⇒ EXTRA (khong SUSPECT).
        Nhung `orderNo` van bi bao MISSING vi no la field `required` ⇒ nguoi doc
        thay ngay, khong can heuristic.
      - `quantity` vs `volume`: doi ten ve NGHA, khong chung ky tu nao ⇒ EXTRA.

    Ket qua: 2 loi nay van bat duoc qua duong `MISSING required`, khong phai qua SUSPECT.
    """
    p2 = {"accountId", "subAccountId", "orderNo", "refId", "nvol", "nprice"}
    assert gate._closest_spec_field("orderId", p2) != "orderNo", (
        "neu heuristic bat duoc `orderId`->`orderNo` thi canh bao o trong co the thu hon"
    )
    spec = json.loads((REPO / "docs/references/openapi-v1.0.0.json").read_text(encoding="utf-8"))
    op = spec["paths"]["/khronos/v1/order/change"]["post"]
    kinds = {k for k, _ in gate.compare({"orderId": "x"}, op)}
    assert "MISSING" in kinds, "duong MISSING van phai bat duoc loi doi ten"
    assert "orderNo" in " ".join(d for _, d in gate.compare({"orderId": "x"}, op))


def test_moi_lech_deu_co_do_phan_loai() -> None:
    spec = json.loads((REPO / "docs/references/openapi-v1.0.0.json").read_text(encoding="utf-8"))
    problems, _ = gate.scan(spec)
    assert problems
    for p in problems:
        assert p.split()[0] in ("EXTRA", "MISSING", "SUSPECT"), p


# ── 4. Exit code ──────────────────────────────────────────────────────────────


def test_gate_xanh_voi_baseline_hien_tai() -> None:
    code, out = _run("--baseline", str(BASELINE))
    assert code == 0, out[-800:]


def test_gate_self_test_pass() -> None:
    code, out = _run("--self-test")
    assert code == 0, out[-800:]
    assert "SELF-TEST PASS" in out


def test_report_luon_exit_0() -> None:
    code, _ = _run("--report", "--baseline", str(BASELINE))
    assert code == 0


# ── 5. HỢP ĐỒNG TIỀN THẬT — bug dang ton tai, khoa lai ───────────────────────
#
# ⚠ Cac test dưới đây KHÔNG phải test "code đúng". Chúng là **tác giả** của bug:
# payload hiện tại KHÔNG khớp spec, và cổng check_tcbs_bodies sẽ báo đỏ nếu ai sửa.
# Khi Owner chốt sửa, các test này **phải sửa theo** — đừng xoá, vì xoá nghĩa là
# quên mất lý do tồn tại.


@pytest.mark.parametrize(
    ("method", "missing_required"),
    [
        ("_gated_place_derivative_order", {"volume", "refId"}),
        ("_gated_change_derivative_order",
         {"accountId", "subAccountId", "orderNo", "refId", "nvol", "nprice"}),
        ("_gated_cancel_derivative_order", {"accountId", "orderNo"}),
    ],
)
def test_bug_dang_ton_tai_field_required_thieu(
    method: str, missing_required: set
) -> None:
    """
    KHÔNG phai "code dung" — day la **ghi nhan lo leech dang co**.

    Spec bao buoc cac field nay; payload hien tai gui thieu ⇒ server TCBS se
    TU CHOI lenh. Chua co JWT nen khong probe duoc. Xem `docs/PLAN_TCBS_ROUND3.md` §0.
    """
    rows = {fn: pl for _w, _p, fn, pl in gate.collect_payloads()}
    assert method in rows, f"{method} khong con trong code"
    payload = rows[method]
    assert missing_required & set(payload) == set(), (
        f"{method} da gui duoc {missing_required & set(payload)} — "
        "cap nhat test + docs/PLAN_TCBS_ROUND3.md + baseline"
    )


def test_requestId_khong_ton_tai_trong_toan_spec() -> None:
    """Tên field ma code gui **khong hề** có trong spec — do bang chung nguyen ban."""
    spec_text = json.dumps(
        json.loads((REPO / "docs/references/openapi-v1.0.0.json").read_text(encoding="utf-8")),
        ensure_ascii=False,
    )
    assert spec_text.count("requestId") == 0
    assert spec_text.count("refId") > 0, "spec phai co refId de doi chieu"