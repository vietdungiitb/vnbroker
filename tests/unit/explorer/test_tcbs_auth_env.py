"""`resolve_auth_token()` phải trả token TCBS **thật**.

Đo live 2026-10-10 (tầng socket, GET-only)
-------------------------------------------
Cùng một endpoint `/tartarus/v1/tickerCommons?symbol=TCB`, hai token:

- ``TCBS_JWT_TOKEN`` (1290 ký tự, 3 phần) → **HTTP 200**, dữ liệu thật
- ``TCBS_AUTH_TOKEN`` (48 ký tự, không phải JWT) → **HTTP 401**
  ``{"code":"validate.token.error","message":"token decode lỗi"}``

Cùng kết quả 401 trên 4/4 endpoint thử. Bản cũ chỉ đọc `TCBS_AUTH_TOKEN`, nên
`TCBSQuote(symbol='TCB').history(...)` ném
``ConnectionError: TCBS iFlash OpenAPI requires valid JWT token`` **trong khi máy
đã có JWT chạy được**.

Test ở đây KHÔNG gọi mạng — chỉ khoá thứ tự ưu tiên và hình dạng token. Bằng
chứng rằng token đó chạy được là ở `docs/REPORT_TIER1_WAVE12.md` §0 C1.
"""

from __future__ import annotations

import os
from unittest.mock import patch

from vnbroker.explorer.tcbs import auth

FAKE_JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dGVzdC1zaWduYXR1cmU"
FAKE_NON_JWT = "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d"


class TestResolveAuthToken:
    def test_jwt_env_wins_over_non_jwt_env(self):
        """JWT thật phải được ưu tiên — đây là thứ làm TCBS hỏng."""
        with patch.dict(
            os.environ,
            {"TCBS_JWT_TOKEN": FAKE_JWT, "TCBS_AUTH_TOKEN": FAKE_NON_JWT},
            clear=False,
        ):
            assert auth.resolve_auth_token() == FAKE_JWT

    def test_jwt_alone_is_enough(self):
        """Chỉ có JWT thì vẫn phải dùng được, không đòi thêm biến nào nữa."""
        with patch.dict(os.environ, {"TCBS_JWT_TOKEN": FAKE_JWT}, clear=False):
            with patch.dict(os.environ, {"TCBS_AUTH_TOKEN": ""}, clear=False):
                assert auth.resolve_auth_token() == FAKE_JWT

    def test_namespaced_jwt_env_is_honoured(self):
        with patch.dict(os.environ, {"vnbroker_TCBS_JWT_TOKEN": FAKE_JWT}, clear=False):
            assert auth.resolve_auth_token() == FAKE_JWT

    def test_non_jwt_is_last_resort_not_first(self):
        """Không có JWT thì mới dùng token cũ — và phải nói rõ nó không phải JWT."""
        with patch.dict(
            os.environ,
            {"TCBS_JWT_TOKEN": "", "vnbroker_TCBS_JWT_TOKEN": "",
             "TCBS_AUTH_TOKEN": FAKE_NON_JWT},
            clear=False,
        ):
            got = auth.resolve_auth_token()
        assert got == FAKE_NON_JWT
        assert got.count(".") != 2, (
            "Token tra ve KHONG co hinh dang JWT. Server tra 401 cho trường hợp "
            "này (đo 2026-10-10) — đừng gọi nó là token hợp lệ."
        )

    def test_explicit_argument_beats_everything(self):
        """Người gọi đã biết mình đang làm gì thì được quyền ghi đè."""
        with patch.dict(os.environ, {"TCBS_JWT_TOKEN": FAKE_JWT}, clear=False):
            assert auth.resolve_auth_token("explicit") == "explicit"

    def test_blank_env_is_treated_as_absent(self):
        """`KEY=` sốt trong `.env` không được thành Bearer rỗng."""
        with patch.dict(
            os.environ,
            {"TCBS_JWT_TOKEN": "   ", "TCBS_AUTH_TOKEN": ""},
            clear=False,
        ):
            assert auth.resolve_auth_token() is None

    def test_resolved_token_looks_like_a_jwt(self):
        """Hình dạng JWT = 3 phần ngăn cách bởi dấu chấm, đếm được không cần decode."""
        with patch.dict(os.environ, {"TCBS_JWT_TOKEN": FAKE_JWT}, clear=False):
            assert auth.resolve_auth_token().count(".") == 2

    def test_env_name_lists_are_tuples(self):
        """`_first_env` duyệt phần tử — chuỗi sẽ bị duyệt thành từng ký tự.

        Lỗi cùng họ với lỗi ở `ProviderPool`: provider biến mất khỏi danh sách
        mà không có cảnh báo.
        """
        assert isinstance(auth.TCBS_JWT_ENV_VARS, tuple)
        assert isinstance(auth.TCBS_NON_JWT_ENV_VARS, tuple)
        for name in auth.TCBS_JWT_ENV_VARS + auth.TCBS_NON_JWT_ENV_VARS:
            assert isinstance(name, str) and name


class TestResolveOpenApiKey:
    def test_reads_the_names_that_exist(self):
        """`TCBS_OPENAPI_API_KEY` là tên thật trong tài liệu iFlash."""
        with patch.dict(os.environ, {"TCBS_OPENAPI_API_KEY": "k1"}, clear=False):
            assert auth.resolve_openapi_api_key() == "k1"

    def test_blank_value_falls_through_to_the_next_name(self):
        with patch.dict(
            os.environ,
            {"TCBS_OPENAPI_API_KEY": "  ", "TCBS_API_KEY": "k2"},
            clear=False,
        ):
            assert auth.resolve_openapi_api_key() == "k2"
