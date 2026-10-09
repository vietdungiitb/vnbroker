"""verify_tcbs_coverage.py — bang do phu API cua TCBS, TAI LAP DUOC.

Tra loi mot cau hoi: trong 48 path cua spec TCBS v1.0.0, path nao da duoc noi vao code,
path nao chua. Dung khi quyet dinh "con endpoint gi de bien" — doc tay vao bang la
nguon sai lon nhat (da sai 1 lan: proposal goi "13 endpoint chua dung", thuc te con 9).

Nguon spec: docs/references/openapi-v1.0.0.json
  sha256 = 7f97d27bde1c6f4b9fb4168bd4ee18c8e9a27fd35e515e3348244e3d2742bd4a
Script tu kiem tra sha256 — neu lech, DO DUNG spec roi chay lai, khong tin ket qua.

Usage:
    python scripts/verify_tcbs_coverage.py            # bang tong hop
    python scripts/verify_tcbs_coverage.py --unused   # chi path chua noi
    python scripts/verify_tcbs_coverage.py --json     # output may doc duoc

Exit code:
    0  spec khop sha256
    1  spec KHONG khop sha256 (can tai lai dung ban spec)
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import pathlib
import re
import sys
from typing import Dict, List

EXPECTED_SHA256 = "7f97d27bde1c6f4b9fb4168bd4ee18c8e9a27fd35e515e3348244e3d2742bd4a"
SPEC_PATH = pathlib.Path(__file__).resolve().parent.parent / "docs" / "references" / "openapi-v1.0.0.json"
PKG_ROOT = pathlib.Path(__file__).resolve().parent.parent / "vnbroker"

# Duoi path xuat hien trong code nhung khong phai REST path day du — bo qua khi
# quet literal de tranh dem nham (tung gay 6 path gia cho trong khi da dung 3).
_LITERAL_PREFIXES = (
    "/nyx", "/gaia", "/khronos", "/ananke", "/hydros", "/physis",
    "/api", "/eros", "/erebos", "/aion", "/akhlys", "/khaos",
    "/campaign-management", "/ws",
)


def normalize(path: str) -> str:
    """Chuan hoa path de so sanh: {param} va :param -> :P, bo dau/cuoi."""
    p = path.strip()
    p = re.sub(r"\{[^}]+\}", ":P", p)
    p = re.sub(r":\w+", ":P", p)
    if not p.startswith("/"):
        p = "/" + p
    return p.rstrip("/").lower() or "/"


def _iter_tcbs_files() -> List[pathlib.Path]:
    files = set(PKG_ROOT.glob("**/tcbs/*.py")) | set(PKG_ROOT.glob("**/*tcbs*.py"))
    return sorted(files)


def _scan() -> tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    """Tra ve (live_paths, removed_paths). Gia tri dict lay tu VALUE, khong phai key.

    `_PATHS` luu ten logic o key ("profile") va path o value — lay key se dem sai 0.
    """
    live: Dict[str, List[str]] = {}
    removed: Dict[str, List[str]] = {}
    for f in _iter_tcbs_files():
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        rel = str(f.relative_to(PKG_ROOT.parent))
        for node in ast.walk(tree):
            name: str | None = None
            value = None
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                name, value = node.targets[0].id, node.value
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                name, value = node.target.id, node.value

            if name and name.isupper() and name.lstrip("_").endswith(("PATHS", "ENDPOINTS")):
                if not isinstance(value, ast.Dict):
                    continue
                target = removed if "REMOVED" in name else live
                for key, val in zip(value.keys, value.values):
                    if isinstance(val, ast.Constant) and isinstance(val.value, str):
                        target.setdefault(normalize(val.value), []).append(
                            f"{rel}:{name}[{key.value if isinstance(key, ast.Constant) else '?'}]"
                        )
                continue

            # Hang string doc lap: path day du viet truc tiep trong code (bars.py,
            # auth.py) — bo qua string nam trong khoi _REMOVED_PATHS.
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                v = node.value.strip()
                if v.startswith(_LITERAL_PREFIXES) and len(v) > 6 and " " not in v:
                    if not any(s.endswith(("_REMOVED_PATHS",)) for s in live.get(normalize(v), [])):
                        live.setdefault(normalize(v), []).append(f"{rel}:LIT{node.lineno}")

    # _REMOVED_PATHS phai thang _REMOVED_PATHS o moi noi, ke ca duoi dang literal.
    for key in removed:
        live.pop(key, None)
    return live, removed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--unused", action="store_true", help="chi in path chua noi")
    parser.add_argument("--json", action="store_true", help="output JSON")
    args = parser.parse_args()

    if not SPEC_PATH.exists():
        print(f"SAI: khong tim thay spec tai {SPEC_PATH}", file=sys.stderr)
        return 1

    raw = SPEC_PATH.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != EXPECTED_SHA256:
        print(f"SAI: spec sha256 lech.", file=sys.stderr)
        print(f"  can   {EXPECTED_SHA256}", file=sys.stderr)
        print(f"  thuc te {digest}", file=sys.stderr)
        return 1

    spec = json.loads(raw.decode("utf-8"))
    spec_norm = {normalize(p): p for p in spec["paths"]}
    live, removed = _scan()

    wired = sorted(spec_norm[n] for n in spec_norm if n in live)
    unused = sorted(spec_norm[n] for n in spec_norm if n not in live and n not in removed)
    ghost = sorted(spec_norm[n] for n in removed if n in spec_norm)

    if args.json:
        print(json.dumps({
            "spec_sha256": digest,
            "spec_paths": len(spec["paths"]),
            "wired": wired,
            "unused": unused,
            "removed_in_spec": ghost,
        }, indent=2, ensure_ascii=False))
        return 0

    if args.unused:
        for p in unused:
            print(p)
        return 0

    print(f"spec sha256 : {digest}  (KHOOP)")
    print(f"spec paths  : {len(spec['paths'])}")
    print(f"da noi      : {len(wired)}")
    print(f"chua noi    : {len(unused)}")
    print(f"_REMOVED_PATHS: {len(removed)} key | van con trong spec: {len(ghost)}")
    if ghost:
        print("\nCANH BAO — path da goi la legacy nhung VAN CO trong spec:")
        for p in ghost:
            print("  !!", p)
    if unused:
        print("\nPath trong spec chua noi vao code:")
        for p in unused:
            print("  -", p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())