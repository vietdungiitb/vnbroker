"""Cổng chặn mojibake (double-encoding UTF-8) trong mã nguồn và tài liệu.

Vì sao có cổng này
-----------------
Ngày 2026-10-16, trong lúc tự kiểm chứng (mutation-test) 4 fix, một script
PowerShell của chính tôi đã hỏng 3 file nguồn:

    $orig = Get-Content -LiteralPath $f -Raw          # doc UTF-8 bằng CP1252
    ... sua ...
    [System.IO.File]::WriteAllText($f, $orig, UTF8)   # ghi lai ban mojibake

PowerShell 5.1 đọc file UTF-8 **không** có `-Encoding` bằng codepage ANSI, nên
tiếng Việt thành `Ghi nháº¯c Ä‘Æ¡n vá»‹` — file vẫn **decode hợp lệ** là UTF-8
(nên mọi gate khác đều xanh!) nhưng nội dung đã hỏng. Hậu quả nặng nhất: hằng
`_SECONDS_NOTE` mất chữ `GIÂY`, tức đúng tài liệu chống lỗi D8 trở nên không
đọc được, và thông điệp `DNSEValidationError` mà người dùng thấy là rác.

Không gate nào hiện có bắt được: ruff PASS, 399 test PASS.

Vì vậy: file mỗi ký tự `Ã Â Ä Æ á €` đi kèm byte 0x80–0xBF là dấu hiệu UTF-8
bị đọc sai rồi mã hoá lại. Script này đếm và **fail** khi >0.

Cách chạy:
    .venv\\Scripts\\python.exe scripts\\check_encoding.py
    .venv\\Scripts\\python.exe scripts\\check_encoding.py --self-test
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

#: Một ký tự Latin-1/Windows-1252 (0xC2-0xC6) theo sau bởi một ký tự trong
#: dải 0x80-0xBF là byte UTF-8 đã bị giải mã sai một lần. `â€` là dạng rút gọn
#: của cùng lỗi (`â€™`, `â€œ`...).
MOJIBAKE = re.compile(r"[\u00c2-\u00c3\u00c4\u00c5\u00c6][\u0080-\u00bf]|\u00e2\u20ac")

#: Chỉ quét nơi mojibake thực sự gây hại. `docs/LESSONS/` và `.venv` bị loại vì
#: chúng chứa trích dẫn byte-level có chủ ý.
SCAN_DIRS = ("vnbroker", "scripts", "tests")
SCAN_SUFFIXES = (".py",)
SCAN_DOCS = ("CLAUDE.md", "CHANGELOG.md", "README.md")


def scan_file(path: Path) -> list[tuple[int, str]]:
    """Trả về ``(dòng, mẫu khớp)`` cho mọi dấu hiệu mojibake trong file."""
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return [(-1, f"khong decode duoc la UTF-8: {exc}")]
    hits: list[tuple[int, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        found = MOJIBAKE.search(line)
        if found:
            hits.append((number, found.group(0)))
    return hits


def iter_targets() -> list[Path]:
    targets: list[Path] = []
    for folder in SCAN_DIRS:
        for path in sorted((REPO / folder).rglob("*")):
            # Chính file này chứa mẫu mojibake **có chủ ý** để tự kiểm chứng,
            # nên nó không thể tự quét chính mình.
            if path.is_file() and path.suffix in SCAN_SUFFIXES and path.name != "check_encoding.py":
                targets.append(path)
    for name in SCAN_DOCS:
        candidate = REPO / name
        if candidate.is_file():
            targets.append(candidate)
    return targets


def run_self_test() -> int:
    """Chứng minh script thật sự FAIL khi dữ liệu hỏng, không chỉ in cảnh báo."""
    cases = [
        # ("nhãn", văn bản, số hit mong đợi)
        ("sach", "Ghi nh\u00e1c \u0111\u01a1n v\u0103ng cho c\u1ea3 5 method", 0),
        # Hai lần mã hoá: "nhắc" -> UTF-8 -> đọc CP1252 -> UTF-8
        ("hai lan", "Ghi nh\u00e1º¯c \u00c4\u2018\u00c6\u00a1n", 1),
        # Dấu câu Windows-1252 bị hỏng: 0x92 0x93 0x94 -> â€™ â€œ â€
        ("smart quote", "ch\u00e0 \u00e2\u20ac\u2122 \u00e2\u20ac\u0153c", 2),
    ]
    failures = 0
    for label, text, expected in cases:
        found = len(MOJIBAKE.findall(text))
        status = "OK" if found == expected else "FAIL"
        if found != expected:
            failures += 1
        print(f"[{status}] {label}: {found} hit (mong doi {expected})")
    print(f"self-test: {len(cases) - failures}/{len(cases)}")
    return 0 if failures == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="fail khi phat hien mojibake")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    offenders: list[str] = []
    scanned = 0
    for path in iter_targets():
        scanned += 1
        for number, sample in scan_file(path):
            relative = path.relative_to(REPO)
            offenders.append(f"  {relative}:{number}  [{sample!r}]")

    if offenders:
        print(f"FAIL: {len(offenders)} dau hieu mojibake (double-encoding UTF-8):")
        print("\n".join(offenders[:40]))
        if len(offenders) > 40:
            print(f"  ... va {len(offenders) - 40} dong nua")
        print()
        print("Nguyen nhan thuong gap: PowerShell 5.1 doc/ghi file UTF-8 khong")
        print("kem -Encoding. KHONG dung `Get-Content -Raw | Set-Content` de sua")
        print("file tieng Viet; dung `read_text('utf-8')` / `write_text('utf-8')`.")
        return 1

    print(f"OK: {scanned} file, khong co mojibake.")
    return 0


if __name__ == "__main__":
    sys.exit(main())