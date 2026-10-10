"""
scripts/check_lessons.py - co bang cho `docs/LESSONS/`.

Thi bang C1/C2/DRIFT cua INDEX.md §1.2. Adapt tu
`vninvestcharts-widget/scripts/check-lessons.cjs`, chuyen sang Python cho khop
stack repo nay (khong co Node trong `scripts/`). Ba sai lech co chu dich, khong
phai la loi:

  1. Doc file theo UTF-8 qua `read_text(encoding="utf-8")`. Console Windows mac
     dinh cp1252 nen in tieng Viet co dau ra `UnicodeEncodeError` — mot gate ma
     nguoi van ban khong doc duoc la mot gate ho cham kiem.
  2. Bo BOM khi dem dong. `Get-Content | Measure-Object -Line` bo dong trong,
     nen dem tay lech 10-29 dong/file voi gate nay. Hai phuong phap cho hai
     con so khac nhau — dung gate nay khi doi chieu.
  3. Regex DRIFT dung `T[^:*\\n]{0,12}:` de chiu ca dau. Regex literal `Tổng`
     that bai neu dau bi mat o noi nao, va mot check DRIFT im lang la
     tuong duong voi khong co check (loi nay bat duoc o lan chay dau tien cua
     ban goc).

Exit code:
    0  sach
    1  co vi pham
    2  KHONG VERIFY DUOC (thu muc rong / khong doc duoc) — TUYET DOI khong doc
       la PASS. Viem co so lieu nua, doc bao cao khong dung, doc sai thi hon la
       gate im lang.

Usage:
    python scripts/check_lessons.py
    python scripts/check_lessons.py --dir <dir>
    python scripts/check_lessons.py --self-test
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parent.parent
DEFAULT_DIR = REPO / "docs" / "LESSONS"
INDEX = "INDEX.md"

C1_MAX_LINES = 120
C2_MAX_LESSONS = 40

# `^## L-<letter><digits>` — KHONG khop `## §1.x`, va khong khop mau format
# trong INDEX (`## L-XX:`) nen mau do khong bao gio bi dem nham la lesson that.
LESSON_HEADING = re.compile(r"^## L-[A-Z]\d+", re.MULTILINE)


def count_nonblank_lines(text: str) -> int:
    """Dem dong that, bo BOM va dong trong. KHONG dung `Measure-Object -Line`."""
    t = text.lstrip("\ufeff").replace("\r\n", "\n").rstrip("\n")
    if not t:
        return 0
    return sum(1 for line in t.split("\n") if line.strip())


def lesson_ids(text: str) -> List[str]:
    return [m.replace("## ", "") for m in LESSON_HEADING.findall(text)]


def check(directory: Path) -> int:
    problems: List[str] = []

    if not directory.is_dir():
        print(f"FAIL: READ  khong tim thay {directory} - KHONG verify duoc.", file=sys.stderr)
        return 2

    try:
        files = sorted(p for p in directory.iterdir() if p.suffix == ".md")
    except OSError as exc:
        print(f"FAIL: READ  khong doc duoc {directory}: {exc}", file=sys.stderr)
        return 2

    if not files:
        print(f"FAIL: READ  {directory} khong co file .md nao - KHONG verify duoc.", file=sys.stderr)
        return 2

    total = 0
    per_file: Dict[str, Tuple[int, int]] = {}

    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            problems.append(f"READ     {path.name} khong doc duoc (UTF-8?): {exc}")
            continue
        lines = count_nonblank_lines(text)
        lessons = 0 if path.name == INDEX else len(lesson_ids(text))
        per_file[path.name] = (lines, lessons)
        if lines > C1_MAX_LINES:
            problems.append(
                f"C1       {path.name} co {lines} dong > {C1_MAX_LINES} - tach them roi"
            )
        if path.name != INDEX:
            total += lessons

    if total > C2_MAX_LESSONS:
        problems.append(
            f"C2       tong {total} lesson > {C2_MAX_LESSONS} "
            f"- gop lesson trung lap, KHONG them file"
        )

    index_path = directory / INDEX
    if not index_path.is_file():
        problems.append(f"MISSING  khong co {INDEX} trong {directory}")
    else:
        idx = index_path.read_text(encoding="utf-8")
        declared = re.search(r"\*\*\s*T[^:*\n]{0,12}:\s*(\d+)\s*lesson", idx)
        if declared and int(declared.group(1)) != total:
            problems.append(
                f"DRIFT    INDEX.md §1.5 ghi tong {declared.group(1)} lesson, "
                f"thuc te la {total}"
            )
        listed = set(re.findall(r"\]\(\./([^)]+\.md)\)", idx))
        for path in files:
            if path.name == INDEX:
                continue
            if path.name not in listed:
                problems.append(f"DRIFT    {path.name} khong duoc ke trong INDEX.md §1.5")

        real_ids = {
            lid
            for name, _ in per_file.items()
            if name != INDEX
            for lid in lesson_ids((directory / name).read_text(encoding="utf-8"))
        }
        for cited in set(re.findall(r"\b(L-[A-Z]\d+)\b", idx)):
            if cited not in real_ids:
                problems.append(
                    f"DRIFT    INDEX.md tro toi {cited} - khong ton tai trong bat ky lesson file"
                )

    if problems:
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        print(f"\ncheck_lessons: {len(problems)} loi.", file=sys.stderr)
        return 1

    detail = " · ".join(
        f"{name} {lines}d/{lessons}bai"
        for name, (lines, lessons) in per_file.items()
        if name != INDEX
    )
    print(
        f"  check_lessons: {len(files)} file | {total}/{C2_MAX_LESSONS} lesson "
        f"| {detail} - sach."
    )
    return 0


# ------------------------------- self-test ---------------------------------
# Self-test KHONG the nao FAIL chung minh gi (L-E06). Moi case chay gate tren
# ban sao tam va assert exit KHAC 0.

_GOOD_INDEX = (
    "# idx\n\n## §1.5\n\n"
    "| [`a.md`](./a.md) | L-E01 |\n\n"
    "**Tổng: 2 lesson**\n"
)
_GOOD_A = "## L-E01: a\n\nx\n\n## L-E02: b\n\ny\n"


def _build(files: Dict[str, str]) -> Path:
    d = Path(tempfile.mkdtemp(prefix="check-lessons-"))
    for name, body in files.items():
        (d / name).write_text(body, encoding="utf-8")
    return d


def _run(args: List[str]) -> Tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def self_test() -> int:
    print("check_lessons SELF-TEST - chay tren ban sao tam, assert gate BAT\n")
    failures = 0
    total_cases = 0

    def probe(name: str, files: Dict[str, str], expect: Optional[str]) -> None:
        nonlocal failures, total_cases
        total_cases += 1
        d = _build(files)
        code, out = _run(["--dir", str(d)])
        import shutil

        shutil.rmtree(d, ignore_errors=True)
        ok = (code == 0) if expect is None else (code != 0 and expect in out)
        if ok:
            print(f"  ok   {name}  exit={code}")
        else:
            failures += 1
            want = "exit 0" if expect is None else f"exit != 0 chua '{expect}'"
            print(f"  FAIL  {name}\n        mong doi {want}, nhan exit={code}\n{out.strip()}")

    good = {"INDEX.md": _GOOD_INDEX, "a.md": _GOOD_A}

    # CONTROL - khong co nay, mot gate hong van bao "tat ca case PASS"
    probe("CONTROL: mau sach", good, None)

    probe("C1: file 121 dong", {**good, "a.md": _GOOD_A + "x\n" * 119}, "C1")

    many = {"INDEX.md": "# idx\n\n**Tổng: 41 lesson**\n"}
    for i in range(1, 42):
        many[f"f{i}.md"] = f"## L-G{i:02d}: t\n\nx\n"
    probe("C2: 41 lesson", many, "C2")

    probe(
        "DRIFT: INDEX khai tong 99",
        {**good, "INDEX.md": _GOOD_INDEX.replace("2 lesson", "99 lesson")},
        "DRIFT",
    )
    probe(
        "DRIFT: lesson file bi bo qua",
        {
            **good,
            "b.md": "## L-E03: c\n\nx\n",
            "INDEX.md": _GOOD_INDEX.replace("**Tổng: 2", "**Tổng: 3"),
        },
        "DRIFT",
    )
    probe(
        "DRIFT: INDEX tro toi lesson khong ton tai",
        {**good, "INDEX.md": _GOOD_INDEX.replace("L-E01", "L-Z99")},
        "DRIFT",
    )
    probe("MISSING: thieu INDEX.md", {"a.md": _GOOD_A}, "MISSING")
    probe("READ: thu muc rong", {}, "khong co file")

    # "Khong verify duoc" la exit 2, TUYET DOI khong phai exit 0
    d = Path(tempfile.mkdtemp(prefix="check-lessons-empty-"))
    code, _ = _run(["--dir", str(d)])
    import shutil

    shutil.rmtree(d, ignore_errors=True)
    total_cases += 1
    if code == 2:
        print("  ok   EXIT 2: khong verify duoc  exit=2")
    else:
        failures += 1
        print(f"  FAIL  EXIT  thu muc rong phai tra 2, nhan {code}")

    if failures:
        print(
            f"\ncheck_lessons SELF-TEST FAILED: {failures}/{total_cases} case. Gate khong duoc tin.",
            file=sys.stderr,
        )
        return 1
    print(f"\ncheck_lessons SELF-TEST PASS: {total_cases} case theo dac ta.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", help="thu muc lesson (mac dinh docs/LESSONS)")
    ap.add_argument("--self-test", action="store_true", help="chung minh gate that su FAIL")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    return check(Path(args.dir) if args.dir else DEFAULT_DIR)


if __name__ == "__main__":
    raise SystemExit(main())