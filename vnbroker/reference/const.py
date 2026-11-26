"""Constants for the CafeF reference layer (anonymous public market data)."""

HOST = "https://cafef.vn"
EXPORT_PATH = "/du-lieu/Ajax/PageNew/DataHistory/PriceHistoryExport.ashx"
JSON_PATH = "/du-lieu/Ajax/PageNew/DataHistory/PriceHistory.ashx"
REFERER = "https://s.cafef.vn/Lich-su-giao-dich-{symbol}-1.chn"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# CafeF prices are in thousand VND; value is in billion VND.
PRICE_SCALE = 1000
VALUE_SCALE = 1_000_000_000

# The JSON endpoint silently caps PageSize at 30.
JSON_PAGE_SIZE = 30
MAX_PAGES = 200

EXCHANGES = ("HOSE", "HNX", "UPCOM")

XLSX_FIELDS = {
    "Mã": "symbol",
    "Ngày": "date",
    "Giá mở cửa": "open",
    "Giá cao nhất": "high",
    "Giá thấp nhất": "low",
    "Giá đóng cửa": "close_raw",
    "Giá điều chỉnh": "close_adjusted",
    "Thay đổi": "change_pct",
    "Khối lượng khớp lệnh": "volume",
    "Giá trị khớp lệnh": "value",
    "Khối lượng thỏa thuận": "put_through_volume",
    "Giá trị thỏa thuận": "put_through_value",
}

JSON_FIELDS = {
    "Symbol": "symbol",
    "Ngay": "date",
    "GiaMoCua": "open",
    "GiaCaoNhat": "high",
    "GiaThapNhat": "low",
    "GiaDongCua": "close_raw",
    "GiaDieuChinh": "close_adjusted",
    "KhoiLuongKhopLenh": "volume",
    "GiaTriKhopLenh": "value",
    "KLThoaThuan": "put_through_volume",
    "GtThoaThuan": "put_through_value",
}

CANONICAL_FIELDS = (
    "symbol",
    "date",
    "open",
    "high",
    "low",
    "close_raw",
    "close_adjusted",
    "change_pct",
    "volume",
    "value",
    "put_through_volume",
    "put_through_value",
)
