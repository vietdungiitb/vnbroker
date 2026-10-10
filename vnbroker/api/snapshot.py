"""
vnbroker/api/snapshot.py

MarketSnapshot — Tổng hợp dữ liệu thị trường cho heatmap & báo cáo danh mục.

Module này gộp ba nguồn dữ liệu thành một JSON list chuẩn hoá:
  1. Bảng giá realtime (KBS Trading.price_board)   → giá, % thay đổi, khối lượng
  2. Danh sách ngành  (KBS Listing.symbols_by_industries) → industry
  3. Tên công ty      (KBS Listing.all_symbols)           → company_name

Schema đầu ra (mỗi phần tử trong list):
  {
    "symbol":        str   — Mã chứng khoán (VD: "VCB")
    "current_price": float — Giá khớp hiện tại (VND, xem "Ghi chú đơn vị")
    "prev_price":    float — Giá tham chiếu hôm qua (cùng đơn vị current_price)
    "change_pct":    float — % thay đổi so với tham chiếu (VD: -1.5)
    "volume":        int   — Khối lượng giao dịch lũy kế (cổ phiếu)
    "market_cap":    float — Vốn hoá thị trường (tỷ VND)
    "industry":      str   — Nhóm ngành tiếng Việt (VD: "Ngân hàng")
    "company_name":  str   — Tên công ty đầy đủ (VD: "Ngân hàng TMCP Ngoại Thương Việt Nam")
  }

Sử dụng:
    from vnbroker import MarketSnapshot

    snap = MarketSnapshot()

    # Lấy dữ liệu cho danh sách mã cụ thể
    data = snap.heatmap_data(["VCB", "TCB", "BID", "CTG"])

    # Lấy dữ liệu cho VN30 (tự động fetch danh sách)
    data = snap.heatmap_data_by_group("VN30")

    # Xuất DataFrame thay vì list
    df = snap.heatmap_df(["VCB", "TCB", "BID"])

Ghi chú đơn vị:
- ``current_price``/``prev_price``: đơn vị **thực** của provider, đọc từ
  ``df.attrs['price_unit']``. Mặc định thư viện là **VND** (đo live 2026-10-10:
  KBS ``price_board(price_unit=None)`` trả ``close_price=56700`` với
  ``attrs['price_unit']=='VND'``, y hệt ``price_unit="VND"``).
- ``market_cap``: **luôn** tỷ VND, dù giá đang ở đơn vị nào:
  ``market_cap = current_price_VND × listed_shares / 1e9``.
- Đổi đơn vị giá bằng ``price_unit="THOUSAND_VND"`` **hoặc** đặt biến môi
  trường ``vnbroker_PRICE_UNIT``; không dùng con số nhân 1000 thủ công.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import pandas as pd

from vnbroker.core.utils.logger import get_logger

logger = get_logger(__name__)

# TTL (giây) cho industry cache — tránh gọi lại API quá nhiều
_INDUSTRY_CACHE_TTL_SECONDS = 300  # 5 phút

# Nhân thêm để đưa giá về VND khi frame đang ở nghìn VND.
_VND_MULTIPLIER = 1_000
_PRICE_UNIT_VND = "VND"
_PRICE_UNIT_THOUSAND_VND = "THOUSAND_VND"


class MarketSnapshot:
    """
    Tổng hợp dữ liệu thị trường từ nhiều nguồn thành một snapshot chuẩn hoá.

    Thiết kế để phục vụ:
      - Heatmap thị trường (treemap theo nhóm ngành)
      - Bảng danh mục (holdings dashboard)
      - API endpoint JSON cho frontend React

    Args:
        source (str): Nguồn dữ liệu. Mặc định "kbs". Hỗ trợ: "kbs".
        random_agent (bool): Dùng user-agent ngẫu nhiên. Mặc định False.
        show_log (bool): Hiển thị log debug. Mặc định False.

    Examples:
        >>> snap = MarketSnapshot()
    >>> data = snap.heatmap_data(["VCB", "VNM", "HPG"])
    >>> print(data[0])
    {
        "symbol": "VCB",
        "current_price": 56700.0,
        "prev_price": 56600.0,
        "change_pct": -0.56,
        "volume": 3049500,
        "market_cap": 473766.78,
        "industry": "Ngân hàng",
        "company_name": "Ngân hàng TMCP Ngoại Thương Việt Nam"
    }
    """

    def __init__(
        self,
        source: str = "kbs",
        random_agent: bool = False,
        show_log: bool = False,
    ) -> None:
        from vnbroker import _ensure_explorer_modules_loaded
        _ensure_explorer_modules_loaded()

        self.source = source.lower()
        self.random_agent = random_agent
        self.show_log = show_log

        # Cache nội bộ: industry và company_name được load 1 lần, refresh sau TTL
        self._industry_cache: Optional[pd.DataFrame] = None
        self._company_cache: Optional[pd.DataFrame] = None
        self._industry_cache_ts: float = 0.0
        self._company_cache_ts: float = 0.0

    # -------------------------------------------------------------------------
    # Public methods
    # -------------------------------------------------------------------------

    def heatmap_data(
        self,
        symbols_list: List[str],
        price_unit: Optional[str] = None,
        refresh_cache: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Trả về JSON list chuẩn cho heatmap với đầy đủ 8 field.

        Args:
            symbols_list: Danh sách mã chứng khoán (VD: ["VCB", "TCB", "VNM"]).
            price_unit: Đơn vị giá đầu ra.
                - None (mặc định): nghìn VND (cách hiển thị phổ biến của HOSE)
                - "VND": Đồng VND nguyên (×1000 so với mặc định)
            refresh_cache: Bắt buộc load lại industry/company cache. Mặc định False.

        Returns:
            List[Dict]: Mỗi phần tử là một dict với 8 field chuẩn.
                        Trả về list rỗng nếu không lấy được dữ liệu giá.

        Raises:
            ValueError: Nếu symbols_list rỗng.

        Examples:
            >>> snap = MarketSnapshot()
            >>> result = snap.heatmap_data(["VCB", "BID", "CTG"])
            >>> # Để lấy giá theo đơn vị VND
            >>> result = snap.heatmap_data(["VCB", "BID"], price_unit="VND")
        """
        if not symbols_list:
            raise ValueError("symbols_list không được để trống.")

        symbols_list = [s.upper() for s in symbols_list]

        df = self._build_snapshot_df(
            symbols_list=symbols_list,
            price_unit=price_unit,
            refresh_cache=refresh_cache,
        )

        if df.empty:
            return []

        return df.to_dict(orient="records")  # type: ignore[no-any-return]

    def heatmap_data_by_group(
        self,
        group: str = "VN30",
        price_unit: Optional[str] = None,
        refresh_cache: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Trả về JSON list chuẩn cho một nhóm chỉ số (VN30, VN100, v.v.).

        Tự động fetch danh sách mã từ KBS, sau đó gọi heatmap_data().

        Args:
            group: Tên nhóm chỉ số. Mặc định "VN30".
                   Hỗ trợ: VN30, VN100, VNMidCap, VNSmallCap, HOSE, HNX, UPCOM, ...
            price_unit: Xem heatmap_data().
            refresh_cache: Xem heatmap_data().

        Returns:
            List[Dict]: Xem heatmap_data().

        Examples:
            >>> snap = MarketSnapshot()
            >>> vn30_data = snap.heatmap_data_by_group("VN30")
            >>> hose_data = snap.heatmap_data_by_group("HOSE")
        """
        from vnbroker.api.listing import Listing

        listing = Listing(source=self.source, random_agent=self.random_agent, show_log=self.show_log)
        symbols_series = listing.symbols_by_group(group=group)

        if symbols_series is None or len(symbols_series) == 0:
            logger.warning(f"Không tìm thấy mã nào cho nhóm '{group}'.")
            return []

        symbols_list = symbols_series.tolist()
        return self.heatmap_data(
            symbols_list=symbols_list,
            price_unit=price_unit,
            refresh_cache=refresh_cache,
        )

    def heatmap_df(
        self,
        symbols_list: List[str],
        price_unit: Optional[str] = None,
        refresh_cache: bool = False,
    ) -> pd.DataFrame:
        """
        Phiên bản trả DataFrame thay vì list — tiện cho phân tích thêm.

        Args:
            symbols_list: Xem heatmap_data().
            price_unit: Xem heatmap_data().
            refresh_cache: Xem heatmap_data().

        Returns:
            pd.DataFrame: Các cột: symbol, current_price, prev_price, change_pct,
                          volume, market_cap, industry, company_name.
                          df.attrs['price_unit'] chứa đơn vị giá hiệu lực.
                          df.attrs['market_cap_unit'] = "tỷ VND" luôn cố định.

        Examples:
            >>> snap = MarketSnapshot()
            >>> df = snap.heatmap_df(["VCB", "VNM", "HPG"])
            >>> df[["symbol", "industry", "market_cap"]].head()
        """
        if not symbols_list:
            raise ValueError("symbols_list không được để trống.")

        symbols_list = [s.upper() for s in symbols_list]

        df = self._build_snapshot_df(
            symbols_list=symbols_list,
            price_unit=price_unit,
            refresh_cache=refresh_cache,
        )
        return df

    def refresh_caches(self) -> None:
        """
        Làm mới toàn bộ cache industry và company_name.

        Gọi method này khi cần đồng bộ lại dữ liệu tĩnh (VD: sau corporate action).

        Examples:
            >>> snap = MarketSnapshot()
            >>> snap.refresh_caches()
        """
        self._industry_cache = None
        self._company_cache = None
        self._industry_cache_ts = 0.0
        self._company_cache_ts = 0.0
        if self.show_log:
            logger.info("Đã xóa cache industry và company_name.")

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _build_snapshot_df(
        self,
        symbols_list: List[str],
        price_unit: Optional[str],
        refresh_cache: bool,
    ) -> pd.DataFrame:
        """
        Pipeline nội bộ: fetch → merge → compute → rename → select.
        """
        # Bước 1: Bảng giá realtime
        price_df = self._fetch_price_board(symbols_list, price_unit)
        if price_df.empty:
            logger.warning("price_board trả về DataFrame rỗng.")
            return pd.DataFrame()

        # Đơn vị giá THỰC của frame, đọc trước khi mọi thao tác cắt/rename làm
        # rơi `attrs`. `price_unit` chỉ là ý muốn của caller: `None` nghĩa là
        # "không ép", và provider rơi về mặc định VND — xem `_compute_market_cap`.
        effective_price_unit = self._effective_price_unit(price_df)

        # Bước 2: Industry map (symbol → industry_name)
        industry_map = self._get_industry_map(refresh=refresh_cache)

        # Bước 3: Company name map (symbol → organ_name)
        company_map = self._get_company_map(refresh=refresh_cache)

        # Bước 4: Tính market_cap (tỷ VND)
        price_df = self._compute_market_cap(price_df, price_unit)

        # Bước 5: Gắn industry và company_name
        price_df["industry"] = price_df["symbol"].map(industry_map).fillna("Khác")
        price_df["company_name"] = price_df["symbol"].map(company_map).fillna(price_df["symbol"])

        # Bước 6: Rename & select output columns
        rename_map = {
            "close_price": "current_price",
            "reference_price": "prev_price",
            "percent_change": "change_pct",
            "volume_accumulated": "volume",
        }
        price_df = price_df.rename(columns=rename_map)

        _OUTPUT_COLS = [
            "symbol",
            "current_price",
            "prev_price",
            "change_pct",
            "volume",
            "market_cap",
            "industry",
            "company_name",
        ]
        available = [c for c in _OUTPUT_COLS if c in price_df.columns]
        df_out = price_df[available].copy()

        # Đảm bảo kiểu dữ liệu
        for col in ("current_price", "prev_price", "change_pct", "market_cap"):
            if col in df_out.columns:
                df_out[col] = pd.to_numeric(df_out[col], errors="coerce")
        if "volume" in df_out.columns:
            df_out["volume"] = pd.to_numeric(df_out["volume"], errors="coerce").astype("Int64")

        # Metadata
        df_out.attrs["price_unit"] = effective_price_unit
        df_out.attrs["market_cap_unit"] = "tỷ VND"
        df_out.attrs["source"] = self.source.upper()

        return df_out

    def _fetch_price_board(
        self,
        symbols_list: List[str],
        price_unit: Optional[str],
    ) -> pd.DataFrame:
        """Fetch bảng giá từ KBS, lấy get_all=True để có listed_shares."""
        from vnbroker.api.trading import Trading

        try:
            trading = Trading(
                source=self.source,
                random_agent=self.random_agent,
                show_log=self.show_log,
            )
            df = trading.price_board(
                symbols_list=symbols_list,
                get_all=True,
                price_unit=price_unit,
            )
            return df if isinstance(df, pd.DataFrame) else pd.DataFrame()
        except Exception as exc:
            logger.error(f"Lỗi khi fetch price_board: {exc}")
            return pd.DataFrame()

    def _compute_market_cap(
        self,
        df: pd.DataFrame,
        price_unit: Optional[str],
    ) -> pd.DataFrame:
        """
        Tính vốn hoá thị trường (tỷ VND).

        Đơn vị giá lấy từ ``df.attrs['price_unit']`` — nhãn **chính provider**
        dán vào lúc chuẩn hoá giá (``core/utils/transform.py``), không đoán
        theo tham số ``price_unit``.

        Vì sao không được đoán (đo live 2026-10-10, KBS, mã VCB):

        - ``price_board(price_unit=None)`` và ``price_board(price_unit="VND")``
          trả **cùng một** ``close_price = 56700`` với
          ``attrs['price_unit'] == "VND"``. Vì ``None`` chỉ có nghĩa là
          *"không ép đơn vị"*, provider rơi về mặc định
          ``vnbroker_PRICE_UNIT`` (= ``VND``).
        - Công thức cũ nhân ``×1000`` khi ``price_unit is None`` ⇒
          ``market_cap = 473 766 777.83`` tỷ thay vì ``473 766.78`` tỷ:
          **phóng đại 1000 lần**, và sai này vẫn là một con số hợp lệ nên
          rất khó phát hiện.

        Hệ quả phải nhớ khi đọc lại dòng này: giá ở **nghìn VND** thì CẦN
        nhân ``×1000`` để về VND; giá đã ở **VND** thì nhân ``×1``. Công thức
        cũ đảo ngược hai nhánh này.

        Args:
            df: Bảng giá đã chuẩn hoá, có ``close_price`` + ``listed_shares``.
            price_unit: Ý muốn của *caller*. Giữ tham số để tương thích, nhưng
                KHÔNG dùng nó để suy ra đơn vị — tham số là ý muốn, nhãn trên
                frame mới là sự thật.

        Returns:
            ``df`` có thêm cột ``market_cap`` (tỷ VND).
        """
        unit = self._effective_price_unit(df)
        multiplier = _VND_MULTIPLIER if unit == _PRICE_UNIT_THOUSAND_VND else 1

        if "close_price" in df.columns and "listed_shares" in df.columns:
            cp = pd.to_numeric(df["close_price"], errors="coerce")
            ls = pd.to_numeric(df["listed_shares"], errors="coerce")
            df = df.copy()
            df["market_cap"] = (cp * multiplier * ls / 1e9).round(2)
        else:
            df = df.copy()
            df["market_cap"] = None

            missing = []
            if "close_price" not in df.columns:
                missing.append("close_price")
            if "listed_shares" not in df.columns:
                missing.append("listed_shares")
            logger.warning(
                f"Không tính được market_cap — thiếu cột: {missing}. "
                f"Kiểm tra KBS price_board get_all=True."
            )

        return df

    @staticmethod
    def _effective_price_unit(df: pd.DataFrame) -> str:
        """Đơn vị giá **thực** của frame, theo thứ tự ưu tiên giảm dần.

        1. ``df.attrs['price_unit']`` — provider dán sau khi chuẩn hoá, đây là
           sự thật về dữ liệu đang nằm trong frame.
        2. ``df.attrs['price_unit_hint']`` — chỉ khi provider tự chủ động ghi.
        3. ``"VND"`` — mặc định của chính thư viện
           (``transform._resolve_target_price_unit``). Chọn VND chứ không phải
           nghìn VND vì đó là giá trị provider **thực sự** trả về khi không
           được ép; chọn ngược lại là phóng đại 1000 lần (đo ở trên).

        Trả về chuẩn hoá về ``"VND"`` / ``"THOUSAND_VND"``.
        """
        raw = df.attrs.get("price_unit") or df.attrs.get("price_unit_hint")
        if not raw:
            return _PRICE_UNIT_VND
        value = str(raw).strip().upper()
        if value in {"THOUSAND", "K", "NGHÌN VND", _PRICE_UNIT_THOUSAND_VND}:
            return _PRICE_UNIT_THOUSAND_VND
        return _PRICE_UNIT_VND

    def _get_industry_map(self, refresh: bool = False) -> Dict[str, str]:
        """
        Trả về dict {symbol: industry_name} từ KBS.
        Có TTL cache 5 phút để tránh gọi lại API liên tục.
        """
        now = time.monotonic()
        if (
            not refresh
            and self._industry_cache is not None
            and (now - self._industry_cache_ts) < _INDUSTRY_CACHE_TTL_SECONDS
        ):
            df = self._industry_cache
        else:
            df = self._fetch_industries()
            self._industry_cache = df
            self._industry_cache_ts = now

        if df is None or df.empty:
            return {}

        return dict(zip(df["symbol"], df["industry_name"]))

    def _get_company_map(self, refresh: bool = False) -> Dict[str, str]:
        """
        Trả về dict {symbol: organ_name} từ KBS.
        Có TTL cache 5 phút.
        """
        now = time.monotonic()
        if (
            not refresh
            and self._company_cache is not None
            and (now - self._company_cache_ts) < _INDUSTRY_CACHE_TTL_SECONDS
        ):
            df = self._company_cache
        else:
            df = self._fetch_company_names()
            self._company_cache = df
            self._company_cache_ts = now

        if df is None or df.empty:
            return {}

        return dict(zip(df["symbol"], df["organ_name"]))

    def _fetch_industries(self) -> pd.DataFrame:
        """Fetch toàn bộ industry map từ Listing."""
        from vnbroker.api.listing import Listing

        try:
            listing = Listing(
                source=self.source,
                random_agent=self.random_agent,
                show_log=self.show_log,
            )
            df = listing.symbols_by_industries()
            if isinstance(df, pd.DataFrame) and not df.empty:
                return df[["symbol", "industry_name"]]
            return pd.DataFrame(columns=["symbol", "industry_name"])
        except Exception as exc:
            logger.error(f"Lỗi khi fetch symbols_by_industries: {exc}")
            return pd.DataFrame(columns=["symbol", "industry_name"])

    def _fetch_company_names(self) -> pd.DataFrame:
        """Fetch toàn bộ company names từ Listing."""
        from vnbroker.api.listing import Listing

        try:
            listing = Listing(
                source=self.source,
                random_agent=self.random_agent,
                show_log=self.show_log,
            )
            df = listing.all_symbols()
            if isinstance(df, pd.DataFrame) and not df.empty:
                # KBS trả về cột organ_name; VCI có thể là organ_name hoặc short_name
                name_col = "organ_name" if "organ_name" in df.columns else df.columns[-1]
                result = df[["symbol", name_col]].copy()
                result = result.rename(columns={name_col: "organ_name"})
                return result
            return pd.DataFrame(columns=["symbol", "organ_name"])
        except Exception as exc:
            logger.error(f"Lỗi khi fetch all_symbols: {exc}")
            return pd.DataFrame(columns=["symbol", "organ_name"])
