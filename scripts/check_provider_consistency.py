"""
scripts/check_provider_consistency.py - co bang tinh nhat quan giua cac danh sach
provider cua tang 1.

Vay tai sao co cong nay (do 2026-10-10, tai `dev @ 9d5db1d`):

  1. `core/provider_pool.py` doc `TCBS_API_KEY` + `TCBS_API_SECRET`. Hai bien
     nay **khong ton tai** trong `.env` nao cua production: `.env` chi co
     `TCBS_JWT_TOKEN`. Provider co credential that bi bo qua, `has_auth_provider
     ('tcbs')` = False, va TCBS khong bao gio vao AUTO.

  2. `core/source_router.py::OPEN_SOURCE_CANDIDATES` la danh sach viet tay.
     Module khong co trong danh sach tra `[]` khi registry **co** provider:
     do thi `screener`/`indices`/`live` deu rong (registry co `kbs`/`vci`/`ssi`).

  3. Hai danh sach do + `ProviderRegistry.list_available` khong bao gio duoc
     doi chieu, nen ca hai sai deu ton tai song song ma khong co gate nao bat.

Cong nay kiem tra **tinh nhat quan**, khong kiem tra tung dong danh sach:

  C1  Provider co credential that trong moi truong VA co implementation trong
      registry => phai xuat hien trong `ProviderPool.get_available_providers`.
  C2  Module nao `ProviderRegistry` co provider => `get_auto_candidates` khong
      duoc tra `[]` (module rong registry thi tra `[]` la dung).
  C3  Provider ma `get_auto_candidates` tra ra phai ton tai trong registry —
      tra ra ten chet thi failover truc tiep den mot provider khong ton tai.

Tinh khong dung credential that: `C1` kiem tren **ten bien** co trong `.env`
va tren class attribute, khong goi mang, khong doc gia tri bien. Cong phai
chay duoc tren may khong co `.env` (CI), nen thieu credential = bo qua, khong
phai loi — nhung van bao loi nao can credential ma dang **thieu mot bien**.

Exit code:
    0  sach
    1  co vi pham
    2  KHONG VERIFY DUOC — TUYET DOI khong doc la PASS
    3  self-test that bai (cong dang bi hong)

Usage:
    python scripts/check_provider_consistency.py
    python scripts/check_provider_consistency.py --self-test
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

REPO = Path(__file__).resolve().parent.parent


def _env_keys_in_env_file(path: Optional[Path] = None) -> Set[str]:
    """Tap ten bien co trong `.env`. KHONG doc/giu gia tri.

    `.env` co the chua credential that; cong nay chi can biet *ten* bien nao
    co mat. Doc theo UTF-8 va bo BOM — console Windows mac dinh cp1252 nen in
    tieng Viet co dau ra `UnicodeEncodeError` (xem `check_lessons.py`).
    """
    env_path = path or (REPO / ".env")
    if not env_path.exists():
        return set()
    keys: Set[str] = set()
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip().lstrip("\ufeff")
        if not line or line.startswith("#") or "=" not in line:
            continue
        keys.add(line.split("=", 1)[0].strip())
    return keys


def _as_env_names(raw: object) -> "tuple[str, ...]":
    """Chuan hoa `raw` ve tuple ten bien.

    `ProviderPool._first_env` duyet **phan tu**, nen neu cau hinh truyen
    mot chuoi thay vi tuple thi no duyet tung ky tu va khong tim thay bien
    nao — provider bien khoi pool ma khong co canh bao. Chinh cong cu
    phat hien ra loai loi do cung de dinh vao no (`for v in config["env_any"]`),
    nen o day luôn chuan hoa ve tuple truoc khi duyet.
    """
    if isinstance(raw, str):
        return (raw,)
    if isinstance(raw, (tuple, list)):
        return tuple(str(v) for v in raw)
    return ()


def _load_env_into_environ() -> bool:
    """Nạp `.env` vào ``os.environ`` (không đè biến đã có).

    `ProviderPool` đọc `os.environ`, còn `.env` là nơi credential thật nằm.
    Không nạp thì gate sẽ báo "có credential" trong khi pool không thấy gì —
    tức báo động giả do chính gate tạo ra. Cách nạp giống hệt
    `tests/conftest.py` và `scripts/probe_tcbs_khronos_readonly.py`.

    KHÔNG in giá trị biến. Trả ``False`` nếu không có `.env`.
    """
    env_path = REPO / ".env"
    if not env_path.exists():
        return False
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip().lstrip("\ufeff")
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())
    return True


def collect_findings() -> Tuple[List[str], List[str]]:
    """Tra `(findings, unverifiable)`.

    `findings` la vi pham that. `unverifiable` la muc KHONG kiem duoc — bao
    cao phai tach rieng, vi "khong co file" khong phai "sach".
    """
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    try:
        from vnbroker.core.provider_pool import ProviderPool
        from vnbroker.core.registry import ProviderRegistry
        from vnbroker.core.source_router import get_auto_candidates
    except Exception as exc:  # pragma: no cover
        return [], [f"khong import duoc vnbroker.core: {type(exc).__name__}: {exc}"]

    try:
        import vnbroker as _vnbroker

        _vnbroker._ensure_explorer_modules_loaded()
    except Exception as exc:  # pragma: no cover
        return [], [f"khong nap duoc explorer modules: {type(exc).__name__}: {exc}"]

    findings: List[str] = []
    unverifiable: List[str] = []

    had_env = _load_env_into_environ()

    pool = ProviderPool()
    env_keys = _env_keys_in_env_file()

    # ---- C1: provider co credential that phai vao duoc pool -----------------
    # "Credential that" = bien co mat trong `.env` HOAC `os.environ`. Chi doc
    # **ten** bien, khong doc gia tri.
    live_env = set(os.environ)
    for name, config in sorted(ProviderPool.AUTH_PROVIDERS.items()):
        env_any = _as_env_names(config.get("env_any"))
        env_all = _as_env_names(config.get("env_all"))

        # C0: cau hinh phai la tap ten bien, khong phai mot chuoi.
        if not env_any:
            findings.append(
                f"C0  provider '{name}' co `env_any` rong hoac sai kieu "
                f"({type(config.get('env_any')).__name__}) — pool khong the "
                f"tim ra credential cua provider nay."
            )
            continue
        if isinstance(config.get("env_any"), str):
            findings.append(
                f"C0  provider '{name}' khai `env_any` la CHUOI "
                f"({config['env_any']!r}) thay vi tuple. `_first_env` duyet theo "
                f"phan tu nen se duyet tung ky tu va khong tim thay bien nao — "
                f"provider bien khoi pool im lang."
            )

        configured = [v for v in env_any if v in env_keys or v in live_env]
        if not configured:
            continue  # provider nay khong duoc cau hinh o may nay -> im lang
        try:
            available = {p.lower() for p in pool.get_available_providers("quote")}
        except Exception as exc:  # pragma: no cover
            unverifiable.append(f"ProviderPool.{name}: {type(exc).__name__}: {exc}")
            continue
        if name not in available:
            findings.append(
                f"C1  provider '{name}' co credential trong moi truong "
                f"({', '.join(configured)}) nhung ProviderPool khong dua no vao "
                f"available providers."
            )
        for module in config["supports"]:
            try:
                mods = {p.lower() for p in pool.get_available_providers(module)}
            except Exception as exc:  # pragma: no cover
                unverifiable.append(f"ProviderPool.{name}/{module}: {exc}")
                continue
            if name not in mods:
                findings.append(
                    f"C1  provider '{name}' khai ho tro module '{module}' "
                    f"nhung ProviderPool khong tra no cho module do."
                )

    # ---- C2 / C3: AUTO candidates phai khop registry ------------------------
    modules: Set[str] = {
        "quote", "company", "financial", "listing", "trading", "news",
        "screener", "indices", "live", "snapshot",
    }

    for module in sorted(modules):
        try:
            registered = {p.lower() for p in ProviderRegistry.list_available(module)}
            candidates = [c.lower() for c in get_auto_candidates(module)]
        except Exception as exc:  # pragma: no cover
            unverifiable.append(f"{module}: {type(exc).__name__}: {exc}")
            continue

        # C2 chi bat khi co provider **pool xac nhan dung duoc**. Module chi co
        # provider can credential (vi du `indices`/`live` chi co `ssi`, ma may
        # nay khong co SSI key) thi `[]` la DUNG — bat no la bao dong gia.
        # Do la thu muc kien: `get_auto_candidates` khoa theo credential, va
        # gate phai khoa theo dung tieu chi do.
        try:
            usable = {p.lower() for p in pool.get_available_providers(module)}
        except Exception as exc:  # pragma: no cover
            unverifiable.append(f"ProviderPool/{module}: {exc}")
            continue
        usable &= registered

        if usable and not candidates:
            findings.append(
                f"C2  module '{module}' co provider dung duoc "
                f"({sorted(usable)}) nhung get_auto_candidates tra [] — "
                f"source='AUTO' cho module nay chet ngay."
            )
        unknown = sorted(set(candidates) - registered)
        if unknown:
            findings.append(
                f"C3  module '{module}': get_auto_candidates tra provider "
                f"{unknown} khong ton tai trong registry "
                f"({sorted(registered)}) — failover se truc tiep den ten chet."
            )

    if not had_env:
        unverifiable.append(
            "khong co .env: C1 chi kiem duoc provider co credential trong "
            "os.environ, phan lon vi pham C1 se khong bi bat tren may nay."
        )

    return findings, unverifiable


def _print(findings: List[str], unverifiable: List[str]) -> int:
    print("=" * 74)
    print("check_provider_consistency — tinh nhat quan danh sach provider tang 1")
    print("=" * 74)
    if unverifiable:
        print("\nKHONG VERIFY DUOC (khong phai la PASS):")
        for item in unverifiable:
            print(f"  - {item}")
    if findings:
        print(f"\nVI PHAM ({len(findings)}):")
        for item in findings:
            print(f"  - {item}")
        return 1
    print("\nOK: khong co vi pham nao.")
    return 2 if unverifiable else 0


# --------------------------------------------------------------------------
# Self-test am: bang chung rang cong THAT BAI khi vi pham xay ra.
# Mot cong chi duoc chay tren input sach la mot cong chua duoc kiem.
# --------------------------------------------------------------------------

NEGATIVE_CASES: Tuple[Tuple[str, str], ...] = (
    (
        "C1 — provider co credential bi pool bo qua",
        "khoi phuc cau hinh TCBS cu (doi `TCBS_JWT_TOKEN` bang "
        "`TCBS_API_KEY` + `TCBS_API_SECRET`) va chi cap `TCBS_API_KEY`. "
        "Dang thay la bo qua credential that, va C1 phai bat.",
    ),
    (
        "C1 — provider bien mat khi bien thu cap vao chuoi",
        "cau hinh DNSE rut gon con mot bien; phai giu dang tuple de "
        "`_first_env` duyet theo bien chu khong theo ky tu.",
    ),
)


def self_test() -> int:
    """Phai chay GREEN tren ban dung va RED tren ban hong.

    Hai truong hop am ben duoi KHONG sua file that: chung khoi phuc cau hinh
    trong bo nho, chay gate, roi khoi phuc lai. Sua file that de lam gate
    do du la cach lam mot gate "chay duoc" ma khong bao gi - dung chinh no.
    """
    findings, unverifiable = collect_findings()
    baseline_code = _print(findings, unverifiable)
    print(f"\nself-test: ban dung -> exit {baseline_code} (mong doi 0)")

    if baseline_code != 0:
        print("self-test THAT BAI: ban dung da do vi pham.")
        return 3

    from vnbroker.core import provider_pool as pp

    saved_config = dict(pp.ProviderPool.AUTH_PROVIDERS)
    saved_env = {k: os.environ.get(k) for k in (
        "TCBS_API_KEY", "TCBS_API_SECRET", "DNSE_API_KEY", "DNSE_API_SECRET",
    )}
    failures: List[str] = []
    try:
        # --- Am 1: cau hinh TCBS cu, chi cap key, khong cap secret -----------
        broken = dict(saved_config)
        broken["tcbs"] = {
            "env_any": ("TCBS_API_KEY",),
            "env_all": ("TCBS_API_SECRET",),
            "supports": ["quote"],
        }
        pp.ProviderPool.AUTH_PROVIDERS = broken  # type: ignore[assignment]
        os.environ.pop("TCBS_API_KEY", None)
        os.environ.pop("TCBS_API_SECRET", None)
        os.environ.pop("TCBS_JWT_TOKEN", None)
        os.environ["TCBS_API_KEY"] = "dummy-key"
        bad, _ = collect_findings()
        if not any(f.startswith("C1  provider 'tcbs'") for f in bad):
            failures.append(
                NEGATIVE_CASES[0][0] + ": gate khong bat duoc config TCBS cu "
                "voi key co mat, secret thieu."
            )
        else:
            print("self-test: am 1 -> RED nhu mong doi (C1 bat config TCBS cu)")

        # --- Am 2: rut gon danh sach bien thanh mot chuoi -------------------
        pp.ProviderPool.AUTH_PROVIDERS = saved_config  # type: ignore[assignment]
        str_bug = dict(saved_config)
        str_bug["dnse"] = {
            "env_any": "DNSE_API_KEY",   # chuoi, KHONG phai tuple
            "env_all": ("DNSE_API_SECRET",),
            "supports": ["quote"],
        }
        pp.ProviderPool.AUTH_PROVIDERS = str_bug  # type: ignore[assignment]
        for k in ("DNSE_API_KEY", "DNSE_API_SECRET"):
            os.environ.pop(k, None)
            os.environ[k] = "dummy"
        bad2, _ = collect_findings()
        if not any(f.startswith("C1  provider 'dnse'") for f in bad2):
            failures.append(
                NEGATIVE_CASES[1][0] + ": gate khong bat duoc danh sach bien "
                "bi rut gon con chuoi."
            )
        else:
            print("self-test: am 2 -> RED nhu mong doi (C1 bat bien rut gon)")
    finally:
        pp.ProviderPool.AUTH_PROVIDERS = saved_config  # type: ignore[assignment]
        for key, value in saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    if failures:
        print()
        for item in failures:
            print(f"self-test THAT BAI: {item}")
        return 3

    print("self-test OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return self_test()

    findings, unverifiable = collect_findings()
    return _print(findings, unverifiable)


if __name__ == "__main__":
    sys.exit(main())
