"""Chuyển thời gian sang đơn vị mà DNSE OpenAPI thật sự chấp nhận.

Vì sao module này tồn tại
------------------------
Đo production 2026-10-16 (không VPN): 5 endpoint phân trang
(`quotes` / `trades` / `expected-price` / `foreign-trading` /
`market-index`) nhận `from`/`to` là **unix GIÂY**. Gửi milliseconds —
tức `int(time.time() * 1000)`, thói quen phổ biến nhất khi lập trình Python —
trả ``400 range exceeds maximum time range``.

Vì các method khai `from_date: int | None` mà **không nói đơn vị**, lỗi đó không
có dấu hiệu gì từ phía vnbroker: kiểu trong là `int`, số trong cũng là `int`, chỉ
server mới biết là sai. Đây là lý do `MARKET_INDEX` cũng cần một ranh giới riêng:
server bắt `from` và `to` phải **cùng một ngày** lịch theo giờ Việt Nam
(``400 from and to must be in the same date``).

Mốc thời gian
-------------
Mọi phép so sánh "cùng ngày" dùng ``Asia/Ho_Chi_Minh``, không phải UTC. Lệch
7 tiếng ⇒ một cửa sổ trong ngày thành "khác ngày" và ngược lại. `datetime` không
kèm tzinfo được hiểu là **giờ VN**, vì đó là mặc định của thị trường này; đọc nó
là UTC sẽ lệch mốc ngày.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Union
from zoneinfo import ZoneInfo

#: Múi giờ quyết định "ngày giao dịch" cho toàn bộ module.
VIETNAM_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

#: Ngưỡng phân biệt giây với milliseconds.
#:
#: Unix **giây** hiện tại ≈ 1.79e9 (≈ 2026). Unix **milliseconds** ≈ 1.79e12.
#: Mốc 1e11 nằm giữa: 1e11 giây là năm **5138**, còn 1e11 milliseconds là năm
#: **1973**. Với mọi dữ liệu thực tế, một số lớn hơn 1e11 chắc chắn là
#: milliseconds. Ngưỡng này được đặt ở giữa khoảng vô tận giả, không phải ở mép.
MILLISECOND_THRESHOLD = 10**11

TimeLike = Union[datetime, date, str, int, float]


def to_unix_seconds(value: TimeLike) -> int:
    """Đưa một mốc thời gian về unix **giây** — đơn vị DNSE yêu cầu.

    Args:
        value: ``datetime`` (naive được hiểu là giờ VN), ``date``, chuỗi ISO
            ``"2026-10-16"`` hoặc ``"2026-10-16T15:00:00"``, hoặc số.
            Số lớn hơn :data:`MILLISECOND_THRESHOLD` được coi là milliseconds và
            chia 1000 — đây là chỗ chặn lỗi đã đo ở trên.

    Returns:
        Số giây kể từ epoch.

    Raises:
        ValueError: khi ``value`` là chuỗi không parse được theo ISO.

    Ghi chú về số nguyên:
        Một số **đã là giây** được giữ nguyên — không có cách nào biết người
        gọi định ý gì, nên giả định "tôi đã tính sẵn". Chỉ có chi tiết
        milliseconds mới được sửa, vì sai hướng đó đã đo được 400.
    """
    if isinstance(value, bool):  # bool là int; chặn trước khi rơi vào nhánh số
        raise TypeError("bool không phải mốc thời gian")

    if isinstance(value, (int, float)):
        numeric = float(value)
        if numeric >= MILLISECOND_THRESHOLD:
            return int(numeric / 1000)
        return int(numeric)

    if isinstance(value, datetime):
        moment = value if value.tzinfo is not None else value.replace(tzinfo=VIETNAM_TZ)
        return int(moment.timestamp())

    if isinstance(value, date):
        return int(datetime.combine(value, time.min, tzinfo=VIETNAM_TZ).timestamp())

    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        return to_unix_seconds(parsed)

    raise TypeError(f"Không chuyển được {type(value).__name__} sang unix giây")


def vn_day_bounds(value: TimeLike) -> tuple[int, int]:
    """Trả ``(mở, đóng)`` của **ngày lịch** chứa ``value``, theo giờ VN.

    Mốc đóng là 23:59:59 của chính ngày đó — dùng nửa đêm của ngày kế tiếp sẽ
    khiến cửa sổ "23:59 hôm nay → 00:05 mai" bị coi là hợp lệ trong khi server
    coi là khác ngày.

    Returns:
        Cặp unix giây ``(00:00:00, 23:59:59)`` theo ``Asia/Ho_Chi_Minh``.
    """
    seconds = to_unix_seconds(value)
    moment = datetime.fromtimestamp(seconds, VIETNAM_TZ)
    start = moment.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1, microseconds=-1)
    return int(start.timestamp()), int(end.timestamp())


def is_same_vn_day(from_seconds: int | None, to_seconds: int | None) -> bool:
    """Hai mốc có rơi vào cùng một ngày lịch giờ VN không.

    Trả ``True`` khi **một** trong hai vế là ``None`` — thiếu thì không có gì để
    mâu thuẫn, và caller đã chọn gửi đi thì để server quyết định. Chặn ở đây thà
    ``False`` sẽ chặn cả những lời gọi hợp lệ không truyền khoảng thời gian.
    """
    if from_seconds is None or to_seconds is None:
        return True
    return datetime.fromtimestamp(from_seconds, VIETNAM_TZ).date() == datetime.fromtimestamp(
        to_seconds, VIETNAM_TZ
    ).date()