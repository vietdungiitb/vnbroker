"""
scripts/check_tcbs_bodies.py - doi chieu PAYLOAD THAT cua moi write method voi spec TCBS.

Vay sao co cua nay: o round 3 phat hien **8 write method gui body KHONG khop spec**.
Da do bang script:
  - `requestId` trong toan spec = **0 lan**
  - `refId`     trong toan spec = **9 lan**
  - `POST /khronos/v1/order/change` spec bat buoc `accountId, subAccountId, orderNo,
    refId, nvol, nprice` - code gui `orderId, quantity, price, requestId`.

Mot field gui thua co the TCBS bo qua. Nhung **thieu field `required`** thi lenh that
bi tu choi. Day la lo loi nguy hiem nhat ma gate test hien co **khong bat duoc**:
test chi assert "payload co key X", khong assert "payload khop spec".

Cong nay doc payload bang **AST** (khong regex) roi so voi
`docs/references/openapi-v1.0.0.json`.

Ba loai lech, tach biet:
  EXTRA    gui field khong ton tai trong spec `properties`
  MISSING  gui thieu mot field trong spec `required`
  SUSPECT  gui field co ten gan voi field `required` (vd `quantity` vs `volume`,
           `orderId` vs `orderNo`) - khi gap, nguoi doc phai tu phan xu

CHAY:
  python scripts/check_tcbs_bodies.py             # exit 1 neu con lech (cong chan)
  python scripts/check_tcbs_bodies.py --report    # in bang lech, exit 0 (lap backlog)
  python scripts/check_tcbs_bodies.py --baseline docs/tcbs_body_baseline.json
  python scripts/check_tcbs_biles.py --self-test  # (viet dung ten: check_tcbs_bodies)

Exit: 0 sach | 1 co lech | 2 KHONG VERIFY DUOC (thieu spec, spec lech sha, khong
tim thay payload nao) - TUYET DOI khong doc la PASS.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parent.parent
SPEC_PATH = REPO / "docs" / "references" / "openapi-v1.0.0.json"
EXPECTED_SHA256 = "7f97d27bde1c6f4b9fb4168bd4ee18c8e9a27fd35e515e3348244e3d2742bd4a"
DEFAULT_BASELINE = REPO / "docs" / "tcbs_body_baseline.json"

TCBS_DIR = REPO / "vnbroker" / "broker" / "tcbs"
WRITE_VERBS = {"post", "put", "patch", "delete"}


# ------------------------------- helpers ----------------------------------


def normalize_path(p: str) -> str:
    p = p.strip()
    p = re.sub(r"\{[^}]+\}", ":P", p)
    p = re.sub(r":\w+", ":P", p)
    if not p.startswith("/"):
        p = "/" + p
    return p.rstrip("/").lower() or "/"


def _gated_body_call(fn: ast.FunctionDef) -> Optional[ast.Dict]:
    """
    Tra ve dict literal la payload cua method write, hoac None.

    Code that tao bien truoc roi moi truyen:
        payload = {"a": 1}
        return self._post(url, payload)
    nen phai **theo bien**, khong chi doc arg inline. (Da gap khi viet lai: doc inline
    thi khong tim thay gi va gate im lang — nguy hiem hon gate bao sai.)

    ⚠ KHONG loai dict vi chua `Call` trong value — `symbol.upper()` la binh thuong.
    """
    # 1. bang bien -> dict literal gan trong body.
    #    ⚠ Phai bat ca `Assign` (`payload = {...}`) LAN `AnnAssign`
    #    (`payload: dict = {...}`). `money.py` va `condition_orders.py` viet
    #    co **annotation** ⇒ chi bat `Assign` se bo sot 4 write method, van
    #    bao xanh. Da gap that o audit round 3.
    var_dict: Dict[str, ast.Dict] = {}
    for node in ast.walk(fn):
        pairs: List[tuple] = []
        if isinstance(node, ast.Assign):
            pairs = [(t, node.value) for t in node.targets]
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            pairs = [(node.target, node.value)]
        for tgt, val in pairs:
            if (
                isinstance(tgt, ast.Name)
                and isinstance(val, ast.Dict)
                and val.keys
                and all(
                    isinstance(k, ast.Constant) and isinstance(k.value, str)
                    for k in val.keys
                )
            ):
                var_dict[tgt.id] = val

    # 2. tim loi goi _post/_put/_write_request/post_json
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else (
            func.id if isinstance(func, ast.Name) else ""
        )
        if name not in ("_post", "_put", "_write_request", "post_json"):
            continue
        # arg vi tri
        for arg in node.args[1:]:
            if isinstance(arg, ast.Dict) and arg.keys:
                if all(isinstance(k, ast.Constant) and isinstance(k.value, str) for k in arg.keys):
                    return arg
            if isinstance(arg, ast.Name) and arg.id in var_dict:
                return var_dict[arg.id]
        # ⚠ KWARG: `self._post(url, payload=payload)` — bo qua `node.keywords` thi
        # method bi bo sot **va gate van bao xanh**. Da gap that o audit round 3.
        for kw in node.keywords:
            if kw.arg is None:
                continue
            if isinstance(kw.value, ast.Dict) and kw.value.keys:
                if all(isinstance(k, ast.Constant) and isinstance(k.value, str)
                       for k in kw.value.keys):
                    return kw.value
            if isinstance(kw.value, ast.Name) and kw.value.id in var_dict:
                return var_dict[kw.value.id]
    return None


def _path_used(
    fn: ast.FunctionDef,
    path_values: Dict[str, str],
    package_index: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """
    File method nay tro toi path spec nao?

    Nhan duoi ca `_PATHS["kieu"]` (bien module) va `self._ORDER_PATHS["kieu"]` (class
    attribute o module khac) - code that duoc ca hai dang nen gate khong duoc chi nhat
    mot. `package_index` la fallback khi key khong ton tai trong module hien tai.
    """
    package_index = package_index or {}
    for node in ast.walk(fn):
        if isinstance(node, ast.Subscript):
            base = node.value
            name = None
            if isinstance(base, ast.Name):
                name = base.id
            elif isinstance(base, ast.Attribute):
                name = base.attr
            if name and name.endswith("PATHS"):
                sl = node.slice
                if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
                    key = sl.value
                    return path_values.get(key) or package_index.get(key)
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            v = node.value.strip()
            if v.startswith("/") and "/" in v[1:] and " " not in v:
                return v
    return None


def _similarity(a: str, b: str) -> int:
    """So phu trung KY TU (khong theo vi tri). Vi tri sai: `orderId` vs `orderNo`
    giong o vi tri 0,1,2,4 nhung lech 5,6,7."""
    from collections import Counter

    return sum((Counter(a.lower()) & Counter(b.lower())).values())


def _closest_spec_field(field: str, props: set) -> Optional[str]:
    """
    Tim field trong spec gan nhat voi `field`, theo do phu trung ky tu.

    Tien thuc:
      `orderId` -> `orderNo` (6/7)      `requestId` -> `refId` (4/5)
      `price`   -> `nprice` (5/5)
    KHONG bat duoc truong doi ten ve NGHA (`quantity` -> `volume`, khong chung ky tu
    nao). Truong hop do gate bao EXTRA + canh bao `volume` la MISSING - nguoi doc
    tu thay. Gate KHONG doan nghia.
    """
    best: Optional[str] = None
    best_score = 0.0
    for p in sorted(props):
        # Che 1 - chieu dai tuong doi. `requestId`(9) vs `side`(4): do phu trung ky tu
        # = 4/4 = 1.0 => tia sai gia nhin "gia nhat". Ten spec phai dai it nhat mot
        # nua ten gui moi dang la kha nang doi ten.
        if len(p) < 0.5 * len(field):
            continue
        score = _similarity(field, p)
        # So TAI SO, khong nhan roi cat: `int(0.8*4)` = 3 kien ty so 0.75 lot nguong.
        ratio = score / max(1, min(len(field), len(p)))
        if ratio < 0.8 or score < 2:
            continue
        if ratio > best_score or (ratio == best_score and best and len(p) < len(best)):
            best, best_score = p, ratio
    return best


# --------------------------------- scan -----------------------------------


def collect_payloads() -> List[Tuple[str, str, str, Dict[str, Any]]]:
    """
    Tra ve danh sach (file, method, path, payload).
    Doc bang AST nen khong nham string trong docstring/comment.

    ⚠ Phai co **fallback toan package**. Sau khi tach `derivative_orders.py`, 5 write
    method lay path tu `self._ORDER_PATHS` (class attribute gan o module khac) thay vi
    `_PATHS` module-level. Khong co fallback thi gate **bo qua 5 method do** va im lang
    bao xanh — con 3 method cua `equity.py` van xanh. Bat ngay o bai test cua chinh S2.
    """
    found: List[Tuple[str, str, str, Dict[str, Any]]] = []

    files = sorted(TCBS_DIR.glob("*.py"))

    # 0) index toan package: key -> path, dung khi module hien tai khong co `_PATHS`
    package_index: Dict[str, str] = {}
    for f in files:
        try:
            t = ast.parse(f.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(t):
            d = None
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
                d = node.value
            elif isinstance(node, ast.AnnAssign) and isinstance(node.value, ast.Dict):
                d = node.value
            if d is None:
                continue
            for k, v in zip(d.keys, d.values):
                if (
                    isinstance(k, ast.Constant)
                    and isinstance(v, ast.Constant)
                    and isinstance(v.value, str)
                    and v.value.startswith("/")
                ):
                    package_index.setdefault(k.value, v.value)

    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue

        path_values: Dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.target.id == "_PATHS" and isinstance(node.value, ast.Dict):
                    for k, v in zip(node.value.keys, node.value.values):
                        if (
                            isinstance(k, ast.Constant)
                            and isinstance(v, ast.Constant)
                            and isinstance(v.value, str)
                        ):
                            path_values[k.value] = v.value
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == "_PATHS" and isinstance(node.value, ast.Dict):
                        for k, v in zip(node.value.keys, node.value.values):
                            if (
                                isinstance(k, ast.Constant)
                                and isinstance(v, ast.Constant)
                                and isinstance(v.value, str)
                            ):
                                path_values[k.value] = v.value

        for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
            for fn in [n for n in cls.body if isinstance(n, ast.FunctionDef)]:
                # Skip lop HTTP: `_post` / `_put` la *tang gui*, khong phai lenh.
                # Neu quet chung, chung se co "payload" rong va duoc dem nham.
                if fn.name in ("_post", "_put", "_write_request", "post_json"):
                    continue
                payload_node = _gated_body_call(fn)
                if payload_node is None:
                    continue
                spec_path = _path_used(fn, path_values, package_index)
                if not spec_path:
                    continue
                payload: Dict[str, Any] = {}
                for k, v in zip(payload_node.keys, payload_node.values):
                    if isinstance(k, ast.Constant) and isinstance(k.value, str):
                        payload[k.value] = (
                            v.value if isinstance(v, ast.Constant) else "<dynamic>"
                        )
                found.append(
                    (
                        f"{path.relative_to(REPO)}:{cls.name}.{fn.name}",
                        spec_path,
                        fn.name,
                        payload,
                    )
                )
    return found


def _looks_semantically_different(a: str, b: str) -> bool:
    """
    Co phai 2 ten chi trung **ky tu** ma khac **nghia** khong?

    `pinCode` vs `price`: chung 4/5 ky tu (`p,i,c,e`) nhung `pinCode` la PIN giao
    dich, `price` la gia. Ratio cao nhung nghia khac hoan toan — truong hop nay
    KHONG duoc ghi "spec goi la `price`", vi nguoi sua theo se gui PIN vao o gia.

    Heuristic: `pin` (va `pinCode`) la truong hop biet truoc. Ngoai ra coi nhu
    cung nghia — dung hon la bao EXTRA (an toan) hon la ghi goi y sai.
    """
    low = a.lower()
    if "pin" in low:
        return True
    return False


def compare(payload: Dict[str, Any], op: Dict[str, Any]) -> List[Tuple[str, str]]:
    """Tra ve danh sach (loai_lech, chi_tiet)."""
    issues: List[Tuple[str, str]] = []
    schema = (
        op.get("requestBody", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema", {})
    )
    props = set(schema.get("properties", {}).keys())
    required = list(schema.get("required", []))
    sent = set(payload.keys())

    for field in sorted(sent - props):
        close = _closest_spec_field(field, props)
        # ⚠ CHỈ gợi ý khi tên nghi sát từ. Neu ten mang **nghia khac** (vd `pinCode`
        # khop 4/5 voi `price` do chung `p,i,c,e`), goi y "doi ten thanh price" se
        # khien nguoi sua **gui PIN giao dich vao o gia** — nguy hiem hon loi hien tai.
        # Vay chi bao EXTRA; `price` van bi bat bang duong `MISSING required`.
        if close and not _looks_semantically_different(field, close):
            issues.append(("SUSPECT", f"`{field}` -> spec goi la `{close}`"))
        else:
            issues.append(("EXTRA", f"`{field}` (khong ton tai trong spec)"))
    for field in required:
        if field not in sent:
            issues.append(("MISSING", f"`{field}` (spec BAT BUOC)"))
    return issues


def scan(spec: Dict[str, Any]) -> Tuple[List[str], int]:
    """Chay toan bo scan. Tra (dong bao loi, so payload tim duoc)."""
    spec_norm = {normalize_path(p): p for p in spec["paths"]}
    problems: List[str] = []
    count = 0

    for where, raw_path, method, payload in collect_payloads():
        norm = normalize_path(raw_path)
        if norm not in spec_norm:
            continue  # path legacy/removed - khong phai pham vi cua cong nay
        real = spec["paths"][spec_norm[norm]]
        matched_verb = False
        for verb, op in real.items():
            if verb.lower() not in WRITE_VERBS:
                continue
            matched_verb = True
            for kind, detail in compare(payload, op):
                problems.append(f"{kind:8} {where}\n         path {spec_norm[norm]} [{verb.upper()}]\n         gui {detail}")
        if not matched_verb:
            continue
        count += 1
    return problems, count


# -------------------------------- report ----------------------------------


def report(problems: List[str], count: int, baseline: Optional[set]) -> int:
    active = [p for p in problems if not _in_baseline(p, baseline)]
    known = len(problems) - len(active)

    for p in problems:
        mark = "KNOWN" if _in_baseline(p, baseline) else "LECH "
        print(f"{mark} {p}")

    print("")
    print(f"  payload write tim thay: {count}")
    print(f"  lech moi            : {len(active)}")
    print(f"  lech da biet (baseline): {known}")
    if active:
        print("")
        print(
            "  -> Server TCBS se TU CHOI lenh thieu field `required`.\n"
            "     Sua truoc, hoac ghi vao baseline neu la no DA BIET va da duoc Owner chap thuan."
        )
    return 1 if active else 0


def _leach_key(problem: str) -> str:
    """
    Khoa dinh danh on dinh: `<KIND> <file>:<Class>.<method> <chi tiet field>`.

    Nhan duoi ca 2 dang dong: co tien do `LECH`/`KNOWN` (khi in report) va khong
    (dong tho tu `scan()`). Sai o day thi key sinh ra la rác (`? EXTRA ...`) va
    baseline kiem tra khong bao gio khop.

    ⚠ Bat buoc **co ca ten field**. Khi chi khoa theo `KIND + method`, mot method da
    bi gan co danh thì MOI field sai them vao deu lot qua im lang — do la gate xanh
    gia. Da bat ngay khi chay fail-truoc: them `totallyBogusField` vao
    `_gated_cancel_derivative_order` van ra `lech moi: 0`.
    """
    lines = [ln.strip() for ln in problem.strip().splitlines() if ln.strip()]
    if not lines:
        return ""
    tokens = lines[0].split(None, 1)
    if len(tokens) == 2 and tokens[0] in ("LECH", "KNOWN"):
        kind, where = tokens[0], tokens[1].strip()
    else:
        kind, where = tokens[0], (tokens[1] if len(tokens) > 1 else "")
    # `where` = `vnbroker\...\file.py:Class.method` - tach phan file ra rieng
    where = where.split()
    kind_and_file = f"{kind} {where[0]}" if where else kind
    detail = ""
    for ln in lines[1:]:
        if ln.startswith("gui "):
            detail = ln[4:].strip()
            break
    return f"{kind_and_file} {detail}".strip()


def _in_baseline(problem: str, baseline: Optional[set]) -> bool:
    if not baseline:
        return False
    return _leach_key(problem) in baseline


def load_baseline(path: Path) -> set:
    if not path.is_file():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    return {str(x) for x in data.get("known_mismatches", [])}


def write_baseline(path: Path, problems: List[str]) -> int:
    """Sinh baseline tu cac lech hien tai. KHONG viet tay — viet tay lech key thi
    gate im lang khong hieu gi (L-E06)."""
    keys = sorted({_leach_key(p) for p in problems})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "_comment": (
                    "Sinh bang `--write-baseline`. Moi dong la 1 payload write method "
                    "da biet sai so voi spec. Xoa dong = gate bat lai ngay."
                ),
                "known_mismatches": keys,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"  da ghi {len(keys)} mismatch vao {path}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="in bang va luon exit 0")
    ap.add_argument("--baseline", help="file baseline json")
    ap.add_argument(
        "--write-baseline", help="sinh baseline tu lech hien tai roi exit 0"
    )
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        from check_tcbs_bodies_selftest import run_self_test  # noqa: PLC0415

        return run_self_test()

    if not SPEC_PATH.is_file():
        print(f"FAIL: READ  khong tim thay spec {SPEC_PATH}", file=sys.stderr)
        return 2
    raw = SPEC_PATH.read_bytes()
    digest = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
    if digest != EXPECTED_SHA256:
        print("FAIL: READ  spec sha256 lech:", file=sys.stderr)
        print(f"  can   {EXPECTED_SHA256}", file=sys.stderr)
        print(f"  thuc te {digest}", file=sys.stderr)
        return 2

    spec = json.loads(raw.decode("utf-8"))
    problems, count = scan(spec)

    if count == 0:
        print("FAIL: READ  khong tim thay payload write nao - KHONG verify duoc.", file=sys.stderr)
        return 2

    if args.write_baseline:
        return write_baseline(Path(args.write_baseline), problems)

    baseline = load_baseline(Path(args.baseline)) if args.baseline else None
    code = report(problems, count, baseline)
    return 0 if args.report else code


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())