"""`Vnbroker.stock()` không được ghi đè token mà provider đã chọn đúng.

Lỗi thứ 5 trong chuỗi TCBS (đo live 2026-10-10)
------------------------------------------------
`common/client.py` từng đọc thẳng `TCBS_AUTH_TOKEN` và truyền xuống làm
`auth_token`, **ghi đè** kết quả của `resolve_auth_token()`. Đo được:

    resolve_auth_token()            -> len 1290  (JWT that, TCBS chay duoc)
    StockComponents.auth_token      -> len 48    (ma khong phai JWT, server 401)
    Vnbroker(source="TCBS").stock("TCB").quote.history()
        -> ConnectionError: TCBS iFlash OpenAPI requires valid JWT token

Trong khi `explorer.tcbs.quote.Quote(symbol="TCB").history()` gọi trực tiếp
với **cùng** `.env` thì trả về 20 dòng. Cùng một máy, cùng một token thật,
hai kết quả khác nhau — vì đường nào đi qua `common/client.py` thì bị ghi đè.

Test ở đây khoá: đường công khai phải dùng **cùng** hàm giải quyết với
provider, và phải ưu tiên JWT.
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from vnbroker import Vnbroker
from vnbroker.explorer.tcbs.auth import resolve_auth_token

JWT = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.c2lnbmF0dXJl"
NON_JWT = "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d"


def _env(**overrides: str) -> dict:
    env = {
        "vnbroker_TCBS_JWT_TOKEN": "",
        "TCBS_JWT_TOKEN": "",
        "vnbroker_TCBS_AUTH_TOKEN": "",
        "TCBS_AUTH_TOKEN": "",
    }
    env.update(overrides)
    return env


class TestStockFacadeToken:
    def test_facade_uses_the_same_resolution_as_the_provider(self):
        """`StockComponents.auth_token` phải bằng `resolve_auth_token()`."""
        with patch.dict(os.environ, _env(TCBS_JWT_TOKEN=JWT), clear=False):
            vn = Vnbroker(source="TCBS")
            stock = vn.stock("TCB")
            assert stock.auth_token == resolve_auth_token() == JWT, (
                f"facade tra token khac provider: {len(stock.auth_token or '')} "
                f"vs {len(resolve_auth_token() or '')}"
            )

    def test_jwt_wins_over_the_non_jwt_env_var(self):
        """Cả hai biến đều có thì JWT phải thắng."""
        with patch.dict(
            os.environ, _env(TCBS_JWT_TOKEN=JWT, TCBS_AUTH_TOKEN=NON_JWT), clear=False
        ):
            vn = Vnbroker(source="TCBS")
            assert vn.stock("TCB").auth_token == JWT

    def test_no_token_in_env_leaves_it_empty_rather_than_inventing_one(self):
        with patch.dict(os.environ, _env(), clear=False):
            vn = Vnbroker(source="TCBS")
            assert vn.stock("TCB").auth_token is None

    def test_non_tcbs_source_does_not_receive_a_tcbs_token(self):
        """Không rò token TCBS sang provider khác."""
        with patch.dict(os.environ, _env(TCBS_JWT_TOKEN=JWT), clear=False):
            vn = Vnbroker(source="VCI")
            assert vn.stock("TCB").auth_token is None


class TestUserFacingMessage:
    """Thông báo lỗi không được chỉ sai biến."""

    @pytest.mark.parametrize(
        "relpath",
        ["vnbroker/explorer/tcbs/quote.py", "vnbroker/explorer/tcbs/bars.py"],
    )
    def test_error_message_points_at_the_jwt_variable(self, relpath):
        """Đo 2026-10-10: `TCBS_AUTH_TOKEN` bị server từ chối 401.

        Hướng dẫn "set TCBS_AUTH_TOKEN=<JWT>" là sai — đọc theo nó thì vẫn 401,
        và người dùng không có cách nào đoán ra phải đổi sang biến khác.
        """
        import pathlib

        source = pathlib.Path(__file__).resolve().parents[3] / relpath
        text = source.read_text(encoding="utf-8")
        assert "TCBS_JWT_TOKEN=<JWT>" in text, (
            f"{relpath} khong chi danh TCBS_JWT_TOKEN trong thong bao loi"
        )
        assert "TCBS_AUTH_TOKEN=<JWT>" not in text, (
            f"{relpath} van chi danh TCBS_AUTH_TOKEN — bien do server tu choi 401"
        )