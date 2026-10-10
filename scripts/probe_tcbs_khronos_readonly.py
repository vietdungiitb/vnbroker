"""
Probe READ-ONLY xac nhan `/khronos/*` co chay duoc khong, va neu khong
thi ly do la GIO GIAO DICH hay QUYEN.

AN TOAN — khong cho phep goi verb ghi, chi GET:
  - Script tu khoi dong: chi `requests.get`.
  - Moi path deu kiem tra la GET, va kiem tra lai path KHONG chua
    tu khoa tao lenh (`place`/`cancel`/`change`/`deposit`/`withdraw`/
    `transfer`/`order` co the tao hoac sua lenh that).
  - Khong co `POST`/`PUT`/`DELETE` trong file nay.

VI SAO CAN SCRIPT NAY:
  Bao cao Round 4 khai "tai khoan thieu derivative scope" — NHUNG do suy ra
  tu claim `scopes` trong JWT, CHUA co 401/503 nao chung minh. Va
  `/tartarus/v1/derivatives` tra 200 that chung to market data phai sinh
  van chay duoc. Nen phai do lai thay do doan.

DUNG:
  .venv\\Scripts\\python.exe scripts\\probe_tcbs_khronos_readonly.py
"""
from __future__ import annotations

import base64
import json
import pathlib
import re
import sys
import time
from datetime import datetime

import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE = "https://openapi.tcbs.com.vn"

# ⚠ KHÔNG hardcode `custodyID` / `accountNo` vào file này — đó là dữ liệu thật
# của khách hàng, commit vào repo là rò rỉ PII. Cả hai đều **lấy lúc chạy**:
# `custodyID` nằm trong claim của chính JWT; `accountNo` lấy từ response API.
CUSTODY_CLAIM = "custodyID"

# Tu khoa co the tao/sua LENH THAT — cam het, ke ca khi chi GET.
# `/khronos/v1/order/in-day` la endpoint DOC duoc phep; `order` trong
# WRITE_GUARD nen phai khai bao ngoai le ro rang.
WRITE_GUARD = re.compile(r"place|cancel|change|deposit|withdraw|transfer", re.I)
READ_ALLOWLIST = {"/khronos/v1/order/in-day"}

# Chi 4 endpoint DOC cua khronos + 2 endpoint doc de so sanh.
PROBES = [
    ("khronos account status      ", "/khronos/v1/account/status", {}),
    ("khronos portfolio status    ", "/khronos/v1/account/portfolio/status", {}),
    ("khronos position close      ", "/khronos/v1/account/portfolio/position/close", {}),
    ("khronos order in-day (DOC)  ", "/khronos/v1/order/in-day", {}),
    ("tartarus derivatives (DOC)  ", "/tartarus/v1/derivatives", {}),
    ("aion account list (DOC)     ", None, {}),  # None -> /aion/v1/customers/{custodyId}/accounts
    ("aion balance (DOC)          ", None, {}),  # None -> /aion/v1/accounts/{accountNo}/se
]


def load_token() -> str:
    env = ROOT / ".env"
    if not env.exists():
        sys.exit("KHONG co .env — can TCBS_JWT_TOKEN.")
    for line in env.read_text(encoding="utf-8").splitlines():
        if line.startswith("TCBS_JWT_TOKEN="):
            tok = line.split("=", 1)[1].strip()
            if tok:
                return tok
    sys.exit("TCBS_JWT_TOKEN rong trong .env — chay getjwt.ps1 de lay token moi.")


def claims(token: str) -> dict:
    seg = token.split(".")[1]
    seg += "=" * (-len(seg) % 4)
    return json.loads(base64.urlsafe_b64decode(seg))


def classify(status: int, body: str) -> str:
    """
    Phan loai ket qua. KHONG doan: moi nhan tieu chi ket luon cho phan loai,
    con lai ghi "HOANG — xem noi dung".
    """
    if status == 200:
        return "OK — route chay"
    if status in (401, 403):
        return "TU CHOI (401/403) — can QUYEN"
    if status == 404:
        return "KHONG TON TAI (404)"
    if status == 500:
        low = body.lower()
        if "không thể thực hiện vào lúc này" in low or "210000" in low:
            return "NGOAI GIO GIAO DICH (500/210000) — can thu lai trong gio"
        if "forbidden" in low or "từ chối" in low:
            return "TU CHOI (500 nen trong) — can QUYEN"
        return "LOI 500 — noi dung xem o duoi"
    if status == 400:
        return "SAI THAM SO (400) — route song, thieu/bad param"
    return f"KHON BIET ({status})"


def main() -> int:
    token = load_token()
    pay = claims(token)

    now = datetime.now()
    ttl_h = (pay["exp"] - now.timestamp()) / 3600 if "exp" in pay else float("nan")
    print("=" * 78)
    print(f"Thoi diem : {now:%Y-%m-%d %H:%M:%S} ({now:%A})")
    print(f"Token    : het han sau {ttl_h:.1f} gio" if ttl_h == ttl_h else "Token    : ?")
    print(f"scopes   : {pay.get('scopes')}")
    print(f"roles    : {pay.get('roles')}  subscription={pay.get('subscription')}")
    print("=" * 78)

    # Giờ giao dịch phái sinh Việt Nam (giờ VN, T2–T6).
    hm = now.hour * 60 + now.minute
    weekend = now.weekday() >= 5
    in_session = (9 * 60 <= hm < 11 * 60 + 30) or (13 * 60 <= hm < 14 * 60 + 45)
    print(f"Gio giao dich VN: {'CO' if in_session and not weekend else 'KHONG'}"
          f"  (T2-T6: 09:00-11:30, 13:00-14:45; hien tai {now:%A})")
    if weekend:
        print("  -> CUOI TUAN: phai sinh VN nghi, moi probe duoc ngay tuong lai.")
    print("-" * 78)

    hdr = {"Authorization": f"Bearer {token}"}

    # `custodyID` lay tu JWT — khong hardcode PII vao file.
    custody = pay.get(CUSTODY_CLAIM)
    account_no: str | None = None
    if not custody:
        print(f"! JWT khong co claim `{CUSTODY_CLAIM}` — bo qua 2 endpoint aion.")
    else:
        r = requests.get(f"{BASE}/aion/v1/customers/{custody}/accounts",
                         headers=hdr, timeout=25)
        if r.status_code == 200 and isinstance(r.json(), list) and r.json():
            account_no = r.json()[0].get("accountNo")
        else:
            print(f"! khong lay duoc accountNo tu /aion ({r.status_code})")

    for label, path, params in PROBES:
        # Hai endpoint `aion` duoc noi o luc chay vi can `custody` / `accountNo`.
        if path is None:
            if "account list" in label:
                if not custody:
                    print(f"[skip] {label} — JWT khong co `{CUSTODY_CLAIM}`")
                    continue
                path = f"/aion/v1/customers/{custody}/accounts"
            else:
                if not account_no:
                    print(f"[skip] {label} — khong lay duoc accountNo")
                    continue
                path = f"/aion/v1/accounts/{account_no}/se"
        # CAM: khong bao gio goi path co the tao/sua lenh that.
        assert path in READ_ALLOWLIST or not WRITE_GUARD.search(path), \
            f"TU CHOI: {path}"
        t0 = time.time()
        try:
            r = requests.get(BASE + path, headers=hdr, params=params, timeout=25)
            status, body = r.status_code, r.text[:160]
        except requests.RequestException as exc:
            status, body = -1, f"{type(exc).__name__}: {exc}"
        ms = int((time.time() - t0) * 1000)
        print(f"[{status:>4}] {label} {ms:>5}ms  {classify(status, body)}")
        print(f"        {body[:150]}")
    print("=" * 78)
    print("DOC YEU CAU GHI VAO BAO CAO:")
    print("  - `account status` = 200            => TAI KHOAN DU QUYEN phai sinh.")
    print("  - `account status` = 500/210000     => ngoai gio giao dich, thu lai.")
    print("  - `account status` = 401/403        => thieu quyen — BAO CAO CHU KHONG")
    print("                                       sua code, do la quyen.")
    print("  - `tartarus derivatives` = 200       => market data phai sinh OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())