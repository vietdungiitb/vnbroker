"""
scripts/check_provider_consistency.py - do bo danh sach provider cua tang 1
co noi dung giua chung khong.

Vay tai sao co cong nay (do 2026-10-10, tai `dev @ 9d5db1d`):

  1. `core/provider_pool.py` doc `TCBS_API_KEY` + `TCBS_API_SECRET`. Hai bien
     nay **khong ton tai** trong `.env` nao cua production: `.env` chi co
     `TCBS_JWT_TOKEN`. Provider co credential that bi bo qua, `has_auth_provider
     ('tcbs')` = False, va TCBS khong bao gio vao AUTO.

  2. `core/source_router.py::OPEN_SOURCE_CANDIDATES` la danh sach viet tay.
     Module khong co trong danh sach tra `[]` khi registry **co** provider.

  3. Ba danh sach (pool / registry / AUTO) khong bao gio duoc doi chieu. Mot
     ban va xoa het `tcbs` khoi `AUTH_PROVIDERS` van chay xanh — do chinh
     audit doc lap da do bang cach xoa muc do va gate im lang.

Cong nay kiem tra **tinh nhat quan**, khong kiem tra tung dong danh sach:

  C0  Cau hinh `env_any`/`env_all` phai la TAP ten bien, khong phai chuoi.
      `_first_env` duyet theo phan tu nen chuoi se bi duyet tung ky tu →
      provider bien mat khoi pool im lang.
  C1  Provider co credential that phai duoc pool nhan dien cho TUNG module
      no khai ho tro.
  C2  Module nao registry co provider **va** pool xac nhan dung duoc thi
      `get_auto_candidates` khong duoc tra `[]`.
  C3  Provider ma `get_auto_candidates` tra ra phai ton tai trong registry.
  C4  Provider da dang ky trong registry, KHONG phai no-auth, thi phai co
      cau hinh credential — cong nay phai bat duoc viec xoa mat cau hinh.

Exit code:
    0  khong co vi pham (co the kem muc KHONG KIEM DUOC — xem canh bao)
    1  co vi pham
    2  gate KHONG CHAY DUOC (khong import duoc vnbroker, khong nap duoc
       explorer). KHONG phai PASS.
    3  self-test that bai (cong dang bi hong)

⚠ Tho `.env` KHONG phai ly do de exit != 0. Khong co `.env` thi cac quy tac
C1/C4 chi kiem duoc mot phan; gate in ra canh bao "chi kiem duoc mot phan" va
van exit 0. Ly do: exit != 0 o day duoc `check_all.ps1` hieu la FAIL, nen quy
tac "khong co .env = khong kiem duoc" se lam mot lenh cua nguoi dun co san bi
doen trong khi bao cao lai in "khong co vi pham nao" — mot dong vua do vua
that. (Do tai kiem doc lap 2026-10-10: `FAIL provider-consistency exit=2
OK: khong co vi pham nao.`)
Mot lan chay KHONG nap `.env` thi cong CHI doc `os.environ`; phai chay qua
`--load-env` (mac dinh khi co file) de kiem day du.

Usage:
    python scripts/check_provider_consistency.py
    python scripts/check_provider_consistency.py --self-test
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

REPO = Path(__file__).resolve().parent.parent

MODULES = (
    "quote",
    "company",
    "financial",
    "listing",
    "trading",
    "news",
    "screener",
    "indices",
    "live",
    "snapshot",
)


# --------------------------------------------------------------------------
# Doc .env — CHI doc TEN bien. Khong bao gio in gia tri.
# --------------------------------------------------------------------------

def _env_path(path: Optional[Path] = None) -> Path:
    return path or (REPO / ".env")


def env_keys_in_env_file(path: Optional[Path] = None) -> Set[str]:
    """Tap ten bien co trong `.env`. KHONG doc/giu gia tri.

    Doc UTF-8 va bo BOM: console Windows mac dinh cp1252 nen in tieng Viet
    co dau ra `UnicodeEncodeError` (xem `check_lessons.py`).
    """
    env_path = _env_path(path)
    if not env_path.exists():
        return set()
    keys: Set[str] = set()
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip().lstrip("\ufeff")
        if not line or line.startswith("#") or "=" not in line:
            continue
        keys.add(line.split("=", 1)[0].strip())
    return keys


def load_env_into_environ(path: Optional[Path] = None) -> bool:
    """Nap `.env` vao `os.environ` (khong de bien da co).

    `ProviderPool` doc `os.environ`, con `.env` la noi credential that nam.
    Khong nap thi cong bao "co credential" trong khi pool khong thay gi — tuc
    bao dong gia do chinh cong tao ra. Cach nap giong het
    `tests/conftest.py` va `scripts/probe_tcbs_khronos_readonly.py`.

    KHONG in gia tri bien. Tra ``False`` neu khong co file.
    """
    env_path = _env_path(path)
    if not env_path.exists():
        return False
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip().lstrip("\ufeff")
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())
    return True


def as_env_names(raw: Any) -> Tuple[str, ...]:
    """Chuan hoa `raw` ve tuple ten bien.

    `ProviderPool._first_env` duyet **phan tu**, nen neu cau hinh truyen mot
    chuoi thi no duyet tung ky tu va khong tim thay bien nao. Chinh cong cu
    phat hien loai loi do cung de dinh vao no, nen o day luôn chuan hoa ve
    tuple truoc khi duyet.
    """
    if isinstance(raw, str):
        return (raw,)
    if isinstance(raw, (tuple, list)):
        return tuple(str(v) for v in raw)
    return ()


# --------------------------------------------------------------------------
# Thu thap phat hien
# --------------------------------------------------------------------------

def _import_core():
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    from vnbroker.core.provider_pool import ProviderPool
    from vnbroker.core.registry import ProviderRegistry
    from vnbroker.core.source_router import get_auto_candidates

    return ProviderPool, ProviderRegistry, get_auto_candidates


def collect_findings(load_env: bool = True) -> Tuple[List[str], List[str]]:
    """Tra `(findings, warnings)`.

    `findings` la vi pham that → gate FAIL. `warnings` la muc KHONG KIEM DUOC
    → van exit 0, nhung phai in ra. Khong tron hai loai: tron la tao ra mot dong
    bao cao vua "OK" vua "khong kiem duoc".
    """
    findings: List[str] = []
    warnings: List[str] = []

    try:
        ProviderPool, ProviderRegistry, get_auto_candidates = _import_core()
    except Exception:
        return [], []  # xu ly o main(): day la truong hop gate khong chay duoc

    try:
        import vnbroker as _vnbroker

        _vnbroker._ensure_explorer_modules_loaded()
    except _GateUnavailable:
        raise
    except Exception as exc:
        raise _GateUnavailable(f"khong nap duoc explorer modules: {type(exc).__name__}: {exc}") from exc

    had_env = load_env_into_environ() if load_env else False
    file_keys = env_keys_in_env_file()
    live_env = set(os.environ)

    # Provider nua gate phai "co credential that" o may nay: bien co mat trong
    # `.env` HOAC trong `os.environ`. Chi doc TEN bien.
    configured_names = {
        name
        for name in file_keys | live_env
    }

    auth_providers = ProviderPool.AUTH_PROVIDERS
    no_auth = {p.lower() for p in ProviderPool.NO_AUTH_PROVIDERS}

    # ---- C0: hinh dang cau hinh -------------------------------------------
    for name in sorted(auth_providers):
        config = auth_providers[name] or {}
        for key in ("env_any", "env_all"):
            if key not in config:
                findings.append(
                    f"C0  provider '{name}' thieu khoa cau hinh '{key}' — "
                    f"pool se nem KeyError khi khoi tao."
                )
                continue
            value = config[key]
            if isinstance(value, str):
                findings.append(
                    f"C0  provider '{name}' khai '{key}' la CHUOI ({value!r}) "
                    f"thay vi tuple. `_first_env` duyet theo phan tu nen se "
                    f"duyet tung ky tu va khong tim thay bien nao — provider "
                    f"bien khoi pool im lang."
                )
            elif value is None or not isinstance(value, (tuple, list)):
                findings.append(
                    f"C0  provider '{name}' khai '{key}' sai kieu "
                    f"({type(value).__name__}); phai la tuple/list."
                )

    # Pool co the nem loi neu cau hinh hong — phai bao loi chu khong de no
    # lam gate so (traceback) ra ngoai.
    try:
        pool = ProviderPool()
    except Exception as exc:
        findings.append(
            f"C0  ProviderPool() nem {type(exc).__name__}: {exc} — cau hinh "
            f"credential hong, khong khoi tao duoc pool."
        )
        return findings, warnings

    # ---- C1: provider co credential that phai vao duoc pool ---------------
    for name in sorted(auth_providers):
        config = auth_providers[name] or {}
        env_any = as_env_names(config.get("env_any"))
        configured = [v for v in env_any if v in configured_names]
        if not configured:
            continue  # provider nay khong duoc cau hinh o may nay -> im lang

        for module in ("quote",) + tuple(config.get("supports") or ()):
            try:
                mods = {p.lower() for p in pool.get_available_providers(module)}
            except Exception as exc:
                findings.append(
                    f"C1  ProviderPool.get_available_providers({module!r}) nem "
                    f"{type(exc).__name__}: {exc}"
                )
                continue
            if name not in mods:
                findings.append(
                    f"C1  provider '{name}' co credential trong moi truong "
                    f"({', '.join(configured)}) nhung pool khong dua no vao "
                    f"module '{module}'."
                )

    # ---- C2 / C3 / C4: AUTO candidates khop registry -----------------------
    for module in MODULES:
        try:
            registered = {p.lower() for p in ProviderRegistry.list_available(module)}
            candidates = [c.lower() for c in get_auto_candidates(module)]
            usable = {p.lower() for p in pool.get_available_providers(module)} & registered
        except Exception as exc:
            findings.append(
                f"C2  module '{module}': {type(exc).__name__}: {exc} — "
                f"khong kiem duoc danh sach AUTO."
            )
            continue

        # C2 chi bat khi co provider **pool xac nhan dung duoc**. Module chi co
        # provider can credential (vi du `indices`/`live` chi co `ssi`, may nay
        # khong co SSI key) thi `[]` la DUNG.
        if usable and not candidates:
            findings.append(
                f"C2  module '{module}' co provider dung duoc "
                f"({sorted(usable)}) nhung get_auto_candidates tra [] — "
                f"source='AUTO' cho module nay chet ngay."
            )

        # C5: provider POOL xac nhan phuc vu duoc module thi PHẢI xuat hien
        # trong AUTO cua module do. Day la invariant bat buoc — dang can nao
        # `get_auto_candidates` noi mot provider o CUOI, provider nao pool
        # dung duoc van khong lo ra khoi AUTO.
        #
        # Chinh quy tac nay bat duoc loi F1: mot ban "chi lap cho trong cho
        # module chua co muc nao" lam TCBS bien mat khoi AUTO o CA 10 module
        # vi 5 module no khai ho tro deu da co muc san. Gate hien tai (chi
        # kiem `usable and not candidates`) im lang truoc truong hop do.
        missing_from_auto = sorted(usable - set(candidates))
        if missing_from_auto:
            findings.append(
                f"C5  module '{module}': pool phuc vu duoc {missing_from_auto} "
                f"nhung get_auto_candidates khong tra ve chung "
                f"(AUTO={candidates}) — provider co credential that bi lo khoi "
                f"dinh tuyen."
            )

        unknown = sorted(set(candidates) - registered)
        if unknown:
            findings.append(
                f"C3  module '{module}': get_auto_candidates tra provider "
                f"{unknown} khong ton tai trong registry "
                f"({sorted(registered)}) — failover se truc tiep den ten chet."
            )

        # C4: provider da dang ky, KHONG no-auth, phai co cau hinh credential.
        # Day la invariant ma viec xoa mot muc khoi `AUTH_PROVIDERS` se lam mat:
        # `C1` duyet `AUTH_PROVIDERS` nen xoa muc = xoa luon quy tac kiem tra.
        for provider in sorted(registered - no_auth):
            if provider not in auth_providers:
                findings.append(
                    f"C4  provider '{provider}' da dang ky cho module "
                    f"'{module}' va khong phai no-auth, nhung khong co muc nao "
                    f"trong ProviderPool.AUTH_PROVIDERS — xoa muc di la bien "
                    f"mat hanh vi check C1, va gate im lang."
                )

    if load_env and not had_env:
        warnings.append(
            "khong co .env: C1/C4 chi kiem duoc provider co credential trong "
            "os.environ. Chay lenh nay tren may co .env de kiem day du."
        )
    if not file_keys and not live_env:
        warnings.append("khong co bien credential nao: phan lon C1/C4 khong kiem duoc.")

    return findings, warnings


class _GateUnavailable(RuntimeError):
    """Gate khong chay duoc (khong import / nap module duoc)."""


# --------------------------------------------------------------------------
# Bao cao
# --------------------------------------------------------------------------

def _print(findings: List[str], warnings: List[str]) -> None:
    print("=" * 74)
    print("check_provider_consistency — tinh nhat quan danh sach provider tang 1")
    print("=" * 74)
    if warnings:
        print("\nKHONG KIEM DUOC (khong phai vi pham, nhung cung khong phai PASS):")
        for item in warnings:
            print(f"  ! {item}")
    if findings:
        print(f"\nVI PHAM ({len(findings)}):")
        for item in findings:
            print(f"  - {item}")
    else:
        print("\nOK: khong co vi pham nao.")


# --------------------------------------------------------------------------
# Self-test am
# --------------------------------------------------------------------------

#: Bien ma self-test se tam do lai. Phai bao day DU moi bien ma no dung.
_SELF_TEST_VARS = (
    "TCBS_JWT_TOKEN",
    "vnbroker_TCBS_JWT_TOKEN",
    "TCBS_AUTH_TOKEN",
    "vnbroker_TCBS_AUTH_TOKEN",
    "TCBS_API_KEY",
    "TCBS_API_SECRET",
    "DNSE_API_KEY",
    "DNSE_API_SECRET",
)


def _run_with_overrides(overrides: Dict[str, Dict[str, Any]]) -> Tuple[List[str], List[str]]:
    """Chay `collect_findings` voi `AUTH_PROVIDERS` tam thay the, roi khoi phuc."""
    from vnbroker.core import provider_pool as pp

    saved = pp.ProviderPool.AUTH_PROVIDERS
    pp.ProviderPool.AUTH_PROVIDERS = overrides  # type: ignore[assignment]
    try:
        return collect_findings()
    finally:
        pp.ProviderPool.AUTH_PROVIDERS = saved  # type: ignore[assignment]


def _expect(overrides: Dict[str, Dict[str, Any]], prefix: str) -> str:
    """Chay gate voi cau hinh hong va tra ve ket qua."""
    findings, _ = _run_with_overrides(overrides)
    return "RED" if any(f.startswith(prefix) for f in findings) else "GREEN"


def self_test() -> int:
    """Phai GREEN tren ban dung va RED tren cau hinh hong.

    KHONG sua file that: chi khoi phuc cau hinh trong bo nho roi tra lai. Sua
    file that de lam gate do du la cach lam mot gate "chay duoc" ma khong bao
    gi — dung chinh no.
    """
    try:
        ProviderPool, _, _ = _import_core()
    except Exception as exc:
        print(f"self-test KHONG CHAY DUOC: {exc}")
        return 3

    findings, warnings = collect_findings()
    _print(findings, warnings)
    if findings:
        print("\nself-test THAT BAI: ban dung da do vi pham.")
        return 3
    print("\nself-test: ban dung -> GREEN (mong doi)")

    good = {name: dict(cfg) for name, cfg in ProviderPool.AUTH_PROVIDERS.items()}
    saved_env = {k: os.environ.get(k) for k in _SELF_TEST_VARS}
    failures: List[str] = []
    try:
        for var in _SELF_TEST_VARS:
            os.environ.pop(var, None)

        # Am 1: cau hinh TCBS cu doi `TCBS_JWT_TOKEN` thanh `TCBS_API_KEY` +
        # `TCBS_API_SECRET`, va chi cap key. Provider phai bien khoi pool.
        os.environ["TCBS_API_KEY"] = "dummy-key"
        os.environ.pop("TCBS_API_SECRET", None)
        broken = {n: dict(c) for n, c in good.items()}
        broken["tcbs"] = {
            "env_any": ("TCBS_API_KEY",),
            "env_all": ("TCBS_API_SECRET",),
            "supports": list(good["tcbs"]["supports"]),
        }
        if _expect(broken, "C1") != "RED":
            failures.append(
                "am 1: cau hinh TCBS cu (doi token bang API key/secret) van "
                "khong bi C1 bat."
            )
        else:
            print("self-test: am 1 -> RED nhu mong doi (C1 bat config TCBS cu)")

        # Am 2: `env_any` rut gon con mot CHUOI.
        str_bug = {n: dict(c) for n, c in good.items()}
        str_bug["dnse"] = {
            "env_any": "DNSE_API_KEY",
            "env_all": ("DNSE_API_SECRET",),
            "supports": list(good["dnse"]["supports"]),
        }
        os.environ["DNSE_API_KEY"] = "dummy"
        os.environ["DNSE_API_SECRET"] = "dummy"
        if _expect(str_bug, "C0") != "RED":
            failures.append("am 2: `env_any` la chuoi van khong bi C0 bat.")
        else:
            print("self-test: am 2 -> RED nhu mong doi (C0 bat env_any la chuoi)")

        # Am 3: `env_all` rut gon con mot CHUOI — truong hop C0 phai bat.
        all_bug = {n: dict(c) for n, c in good.items()}
        all_bug["dnse"] = {
            "env_any": ("DNSE_API_KEY",),
            "env_all": "DNSE_API_SECRET",
            "supports": list(good["dnse"]["supports"]),
        }
        if _expect(all_bug, "C0") != "RED":
            failures.append("am 3: `env_all` la chuoi van khong bi C0 bat.")
        else:
            print("self-test: am 3 -> RED nhu mong doi (C0 bat env_all la chuoi)")

        # Am 4: THIEU khoa cau hinh — gate phai bao loi, khong duoc nem traceback.
        missing = {n: dict(c) for n, c in good.items()}
        missing["dnse"] = {"env_any": ("DNSE_API_KEY",), "supports": ["quote"]}
        try:
            bad_findings, _ = _run_with_overrides(missing)
            if not any(f.startswith("C0") for f in bad_findings):
                failures.append("am 4: thieu khoa `env_all` van khong bi C0 bat.")
            else:
                print("self-test: am 4 -> RED nhu mong doi (C0 bat thieu khoa)")
        except Exception as exc:
            failures.append(
                f"am 4: gate nem {type(exc).__name__} thay vi bao loi: {exc}"
            )

        # Am 5: XOA MOT provider khoi AUTH_PROVIDERS trong khi registry van
        # con — C4 phai bat. Day la truong hop ma cong ban dau khong bat.
        dropped = {n: dict(c) for n, c in good.items() if n != "tcbs"}
        os.environ["TCBS_JWT_TOKEN"] = "a.b.c"
        os.environ["TCBS_API_KEY"] = ""
        os.environ["TCBS_API_SECRET"] = ""
        if _expect(dropped, "C4") != "RED":
            failures.append(
                "am 5: xoa muc TCBS khoi AUTH_PROVIDERS van khong bi C4 bat — "
                "gate im lang dung truong hop can bat."
            )
        else:
            print("self-test: am 5 -> RED nhu mong doi (C4 bat muc bi xoa)")
    finally:
        from vnbroker.core import provider_pool as pp

        pp.ProviderPool.AUTH_PROVIDERS = good  # type: ignore[assignment]
        for key, value in saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        lost_after = [k for k in _SELF_TEST_VARS if k not in os.environ]
        if lost_after:
            print(
                "self-test CANH BAO: cac bien sau khong duoc khoi phuc: "
                f"{lost_after}"
            )

    if failures:
        print()
        for item in failures:
            print(f"self-test THAT BAI: {item}")
        return 3

    print("self-test OK")
    return 0


# --------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate tinh nhat quan provider tang 1.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument(
        "--no-load-env",
        action="store_true",
        help="Khong nap .env vao os.environ (chi doc os.environ hien tai)",
    )
    args = parser.parse_args()

    if args.self_test:
        return self_test()

    try:
        findings, warnings = collect_findings(load_env=not args.no_load_env)
    except _GateUnavailable as exc:
        print("=" * 74)
        print("check_provider_consistency — GATE KHONG CHAY DUOC (KHONG phai PASS)")
        print("=" * 74)
        print(f"  ! {exc}")
        return 2
    except Exception as exc:  # config hong lam gate so ra
        print("=" * 74)
        print("check_provider_consistency — GATE KHONG CHAY DUOC (KHONG phai PASS)")
        print("=" * 74)
        print(f"  ! khong thu duoc cac quy tac: {type(exc).__name__}: {exc}")
        return 2

    _print(findings, warnings)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())