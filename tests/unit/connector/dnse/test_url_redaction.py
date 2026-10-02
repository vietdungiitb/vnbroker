"""P2: URL có credential trong query string không được ghi ra log nguyên văn.

Bối cảnh
--------
Client HMAC (DNSE, KBS) truyền credential TRONG query string:
``wss://...?api_key=...&signature=...``. ``connector/dnse/websocket.py:92``
log URL đó ở level ``INFO`` — mặc định bật — nên ``api_key`` và chữ ký HMAC
bị ghi ra log, và log thường được gom lại/lưu lâu/chuyển tiếp.

Hợp đồng:
1. ``Redactor.redact_url()`` thay mọi giá trị param nhạy cảm.
2. Code đường ghi log dùng nó.
"""

from __future__ import annotations

from vnbroker.broker.security.redaction import Redactor


def test_redacts_api_key_and_signature() -> None:
    url = (
        "wss://stream.dnse.com.vn/ws?api_key=AKIA1234567890ABCD"
        "&signature=deadbeefcafe1234&type=quote"
    )
    out = Redactor.redact_url(url)

    assert "AKIA1234567890ABCD" not in out, f"api_key còn lộ: {out}"
    assert "deadbeefcafe1234" not in out, f"signature còn lộ: {out}"
    # Query-string dùng sentinel không cần URL-encode ("***" sẽ ra %2A%2A%2A)
    assert Redactor.REDACTED_QS in out


def test_keeps_non_sensitive_params() -> None:
    """Chỉ redact param nhạy cảm — không mất thông tin vận hành cần giữ."""
    url = "wss://stream.dnse.com.vn/ws?api_key=SECRET&type=quote&symbol=ACB"
    out = Redactor.redact_url(url)

    assert "type=quote" in out
    assert "symbol=ACB" in out
    assert "SECRET" not in out


def test_url_without_query_is_unchanged() -> None:
    assert Redactor.redact_url("wss://stream.dnse.com.vn/ws") == (
        "wss://stream.dnse.com.vn/ws"
    )


def test_empty_or_malformed_is_safe() -> None:
    assert Redactor.redact_url("") == ""
    assert Redactor.redact_url("not a url") == "not a url"


def test_case_and_dash_insensitive_key_matching() -> None:
    """`API-Key`/`apikey` vẫn phải bị redact."""
    for key in ("API-Key", "apikey", "api_key", "Api_Secret", "trading-token"):
        out = Redactor.redact_url(f"https://h/ws?{key}=LEAKME")
        assert "LEAKME" not in out, f"param {key!r} không được redact: {out}"


def test_dnse_websocket_does_not_log_raw_url() -> None:
    """Source phải redact URL trước khi log — kiểm bằng AST, không chạy network."""
    import ast
    from pathlib import Path

    path = Path(__file__).resolve().parents[4] / (
        "vnbroker/connector/dnse/websocket.py"
    )
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)

    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        # logger.info(...)/warning(...)/debug(...)
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr in {"info", "warning"}):
            continue
        seg = ast.get_source_segment(src, node) or ""
        # f-string chứa biến `url` mà không qua Redactor
        if "url" in seg and "redact_url" not in seg and "Redactor" not in seg:
            offenders.append(seg.splitlines()[0][:90])

    assert not offenders, (
        "Log URL nguyên văn (có thể chứa api_key):\n  " + "\n  ".join(offenders)
    )