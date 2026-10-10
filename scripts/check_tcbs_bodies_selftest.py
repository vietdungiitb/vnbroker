"""
Self-test cho `check_tcbs_bodies.py`.

Nguyen tac: self-test KHONG the nao FAIL chung minh gi (L-E06). Moi case tao ban sao
tam cua spec + module tam roi chay gate, assert exit **KHAC 0** neu mong doi vay.

Case:
  CONTROL   spec + payload khop            -> exit 0
  EXTRA     gui field khong co trong spec  -> exit != 0
  MISSING   thieu field `required`          -> exit != 0
  SUSPECT   ten sai gan (`quantity` vs `volume`) -> exit != 0
  EMPTY     khong co payload write nao      -> exit 2
  SHA       spec lech sha256                -> exit 2
  REPORT    --report luon exit 0            -> exit 0
  BASELINE  lech da biet + baseline         -> exit 0
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Optional, Tuple

HERE = Path(__file__).resolve().parent
GATE = HERE / "check_tcbs_bodies.py"
EXPECTED_SHA = "7f97d27bde1c6f4b9fb4168bd4ee18c8e9a27fd35e515e3348244e3d2742bd4a"

# Spec goc cua repo - dung nguyen ban de sha khop.
REAL_SPEC = HERE.parent / "docs" / "references" / "openapi-v1.0.0.json"


def _module_source(payload_fields: Dict[str, str], path_value: str = "/khronos/v1/order/place") -> str:
    """Sinh module gia co 1 method write gui payload_fields vao path spec cho truoc."""
    body = "\n".join(f'        "{k}": {v},' for k, v in payload_fields.items())
    return f'''
_PATHS = {{"p": "{path_value}"}}


class FakeService:
    def __init__(self, base):
        self._base = base

    def place(self, dry_run: bool = True):
        payload = {{
{body}
        }}
        return self._post(self._base + _PATHS["p"], payload)
'''


def _run(dirpath: Path, extra: Optional[list] = None) -> Tuple[int, str]:
    # Phai chay ban script DA COPY trong ban sao tam. Chay `GATE` (ban that) se
    # quet repo that va moi case deu ra ket qua giong nhau — self-test vo dung.
    cmd = [sys.executable, str(dirpath / "scripts" / "check_tcbs_bodies.py")]
    cmd += extra or []
    proc = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(dirpath), shell=False,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _build(tmp: Path, module_src: str, spec_path: Path) -> None:
    tcbs = tmp / "vnbroker" / "broker" / "tcbs"
    tcbs.mkdir(parents=True, exist_ok=True)
    (tcbs / "derivatives.py").write_text(module_src, encoding="utf-8")
    (tcbs / "__init__.py").write_text("", encoding="utf-8")
    scripts = tmp / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / "check_tcbs_bodies.py").write_text(
        GATE.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (scripts / "check_tcbs_bodies_selftest.py").write_text(
        (HERE / "check_tcbs_bodies_selftest.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    docs = tmp / "docs" / "references"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "openapi-v1.0.0.json").write_bytes(spec_path.read_bytes())


def run_self_test() -> int:
    print("check_tcbs_bodies SELF-TEST - chay tren ban sao tam, assert gate BAT\n")
    failures = 0
    cases = 0

    def probe(name: str, payload: Dict[str, str], expect_code: Optional[int],
              expect_text: Optional[str] = None, extra_args=None) -> None:
        nonlocal failures, cases
        cases += 1
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            try:
                _build(tmp, _module_source(payload), REAL_SPEC)
                code, out = _run(tmp, extra_args)
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print(f"  FAIL  {name}\n        setup loi: {exc}")
                return
        ok = (code == expect_code) if expect_text is None else (code != 0 and expect_text in out)
        if ok:
            print(f"  ok   {name}  exit={code}")
        else:
            failures += 1
            want = f"exit={expect_code}" if expect_text is None else f"exit!=0 chua '{expect_text}'"
            print(f"  FAIL  {name}\n        mong doi {want}, nhan exit={code}\n{out.strip()[:600]}")

    # /khronos/v1/order/place: props = accountId, subAccountId, side, symbol, price,
    # volume, orderType, refId ; required giu `refId`.
    good = {
        "accountId": '"105C1"', "subAccountId": '"D1"', "symbol": '"FPT"',
        "side": '"LONG"', "orderType": '"LIMIT"', "volume": "100",
        "price": "10", "refId": '"r1"',
    }

    probe("CONTROL: payload khop spec", good, 0)
    # `zzz_bogus` khong giong gi -> EXTRA that.
    probe("EXTRA: gui field la", {**good, "zzz_bogus": '"x"'}, 1, "EXTRA")
    probe("MISSING: thieu refId (bat buoc)",
          {k: v for k, v in good.items() if k != "refId"}, 1, "MISSING")
    # `requestId` -> `refId` la nghi SAI DUNG: spec goi truong idempotency la `refId`.
    # Gate tu dong chi ra duoc cap doi nay.
    probe("SUSPECT: requestId -> refId", {**good, "requestId": '"x"'}, 1, "SUSPECT")
    # `orderNo` vs `orderId`: heuristic SUSPECT (do phu trung ky tu).
    # KHONG dung `quantity` vs `volume` o day - doi ten ve NGHA, gate bao EXTRA
    # + canh bao `volume` MISSING; nguoi doc tu thay. Gate khong doan nghia.
    probe(
        "SUSPECT: orderId thay vi orderNo",
        {
            **{
                k: v for k, v in {
                    "accountId": '"105C1"', "subAccountId": '"D1"', "orderNo": '"N1"',
                    "refId": '"r1"', "nvol": "10", "nprice": "12",
                }.items()
            },
            "orderId": '"N1"',
        },
        1,
        "SUSPECT",
    )
    probe("REPORT: --report luon exit 0",
          {**good, "zzz_bogus": '"x"'}, 0, None, ["--report"])

    # EMPTY - module khong co method write nao
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        cases += 1
        try:
            _build(tmp, "X = 1\n", REAL_SPEC)
            code, out = _run(tmp)
        except Exception as exc:  # noqa: BLE001
            code, out = -1, str(exc)
        if code == 2:
            print("  ok   EMPTY: khong co payload -> exit 2  exit=2")
        else:
            failures += 1
            print(f"  FAIL  EMPTY: mong doi exit 2, nhan {code}")

    # SHA - spec tam khac dung -> exit 2
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        cases += 1
        try:
            spec = json.loads(REAL_SPEC.read_text(encoding="utf-8"))
            spec["paths"]["/khronos/v1/order/place"]["post"]["summary"] = "tam sua"
            alt = tmp / "alt.json"
            alt.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
            _build(tmp, _module_source(good), alt)
            code, out = _run(tmp)
        except Exception as exc:  # noqa: BLE001
            code, out = -1, str(exc)
        if code == 2:
            print("  ok   SHA: spec lech sha256 -> exit 2  exit=2")
        else:
            failures += 1
            print(f"  FAIL  SHA: mong doi exit 2, nhan {code}\n{out.strip()[:400]}")

    # BASELINE - lech da biet duoc baseline -> exit 0
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        cases += 1
        try:
            _build(tmp, _module_source({**good, "requestId": '"x"'}), REAL_SPEC)
            baseline = tmp / "b.json"
            subprocess.run(  # noqa: S603 - goi chinh python.exe cua bo test
                [sys.executable, str(tmp / "scripts" / "check_tcbs_bodies.py"),
                 "--write-baseline", str(baseline)],
                capture_output=True, text=True, encoding="utf-8", cwd=str(tmp), shell=False,
                check=False,
            )
            code, out = _run(tmp, ["--baseline", str(baseline)])
        except Exception as exc:  # noqa: BLE001
            code, out = -1, str(exc)
        if code == 0:
            print("  ok   BASELINE: lech da biet -> exit 0  exit=0")
        else:
            failures += 1
            print(f"  FAIL  BASELINE: mong doi exit 0, nhan {code}\n{out.strip()[:500]}")

    if failures:
        print(
            f"\ncheck_tcbs_bodies SELF-TEST FAILED: {failures}/{cases} case. Gate khong duoc tin.",
            file=sys.stderr,
        )
        return 1
    print(f"\ncheck_tcbs_bodies SELF-TEST PASS: {cases} case theo dac ta.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_self_test())