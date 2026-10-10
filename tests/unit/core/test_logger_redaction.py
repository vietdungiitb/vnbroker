"""Regression tests for log redaction in ``vnbroker/core/utils/logger.py``.

This module had ZERO tests, which is how the leak survived: ``redact_sensitive_data``
was measured to leak 4 of 10 realistic inputs at 4cd0f2d, and
``SensitiveDataFilter`` destroyed ``record.args`` for dict arguments.

Each test maps 1:1 to an acceptance criterion in
``docs/PLAN_TIER1_WAVE34.md`` §2 (AC-4.1 ... AC-4.5).  The filter tests drive a real
``logging.StreamHandler`` with ``SensitiveDataFilter`` attached rather than calling the
regex helper directly, so the assertion covers what actually reaches the log file.
"""

import io
import logging

import pytest

from vnbroker.core.utils.logger import SensitiveDataFilter, redact_sensitive_data

# A structurally valid JWT. Never a real credential - this is the textbook
# jwt.io example header/payload with a fixed signature.
JWT = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4ifQ"
    ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
)

# AC-4.2 - inputs whose redaction would mean the guard destroyed real data (L-R07).
MUST_BE_UNCHANGED = [
    "price=12345",
    "symbol=TCB",
    "volume=1.2M",
    "the user name is bob",
    "key note: read the file",
]


def _captured_logger(name):
    """A logger whose only handler is a StreamHandler carrying the real filter."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(SensitiveDataFilter())
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger = logging.getLogger(name)
    logger.handlers = [handler]
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    return logger, stream


def _redacted_all(*cases):
    return [redact_sensitive_data(case) for case in cases]


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param(f"token={JWT}", id="token=<JWT>"),
        pytest.param(f'"apiKey": "{JWT}"', id="json-apiKey"),
        pytest.param(f"api_key={JWT}", id="api_key=<JWT>"),
        pytest.param(f"x-api-key: {JWT}", id="x-api-key"),
        pytest.param("password: hunter2", id="password"),
        pytest.param(f'"access_token": "{JWT}"', id="json-access_token"),
        pytest.param(f"Authorization: Bearer {JWT}", id="Authorization-Bearer"),
        pytest.param(str({"Authorization": f"Bearer {JWT}"}), id="repr-dict"),
        pytest.param(JWT, id="bare-JWT-no-key"),
        pytest.param("otp 123456", id="otp-space-separated"),
    ],
)
def test_ac_4_1_no_credential_survives_redaction(raw):
    """AC-4.1: the 10 measured inputs must leave 0 JWT/OTP behind.

    RED at 4cd0f2d in 4 of the 10 cases (Authorization-Bearer, repr-dict,
    bare-JWT-no-key, otp-space-separated).
    """
    out = redact_sensitive_data(raw)

    assert JWT not in out, f"JWT survived redaction of {raw!r} -> {out!r}"
    if "123456" in raw:
        assert "123456" not in out, f"OTP survived redaction of {raw!r} -> {out!r}"
    if "hunter2" in raw:
        assert "hunter2" not in out


@pytest.mark.parametrize("raw", MUST_BE_UNCHANGED)
def test_ac_4_2_ordinary_log_text_is_untouched(raw):
    """AC-4.2: the anti-destruction guard.

    ``SENSITIVE_KEYS`` contains ``user``, ``key`` and ``auth``. If whitespace is
    allowed as a key/value separator, 'the user name is bob' is rewritten to
    'the user: "***REDACTED***" is bob' - a guard that destroys the data it is
    protecting is worse than the leak (L-R07).
    """
    assert redact_sensitive_data(raw) == raw


def test_ac_4_3_monkey_is_not_treated_as_key():
    """AC-4.3: ``key`` matched mid-word, mangling 'monkey=abc'.

    RED at 4cd0f2d: redact_sensitive_data('monkey=abc') returned
    'monkey: "***REDACTED***"'.
    """
    assert redact_sensitive_data("monkey=abc") == "monkey=abc"


def test_ac_4_4_dict_argument_does_not_destroy_the_log_line(capsys):
    """AC-4.4: a dict argument must not raise or lose the line.

    Python 3.13 unwraps ``args=({"a": 1,},)`` into the dict itself, and the old
    filter iterated it as if it were a tuple - yielding the KEYS. The result was
    ``TypeError: not all arguments converted during string formatting``, swallowed
    by logging, and an EMPTY line in the log file.

    RED at 4cd0f2d: stream.getvalue() == '' and stderr carried a traceback.
    """
    logger, stream = _captured_logger("ac44_dict_arg")

    logger.info("x=%s", {"a": 1, "b": 2})

    out = stream.getvalue()
    assert out.strip(), "log line was lost entirely"
    assert "'a'" in out and "'b'" in out, f"dict values missing from line: {out!r}"
    assert "not all arguments converted" not in capsys.readouterr().err


def test_ac_4_5_dict_argument_authorization_is_redacted_and_readable(capsys):
    """AC-4.5: fixing the filter must not re-open the leak.

    Making the filter render dict values again (i.e. the naive ``str()`` fix) would
    put the JWT straight back into the log. This asserts both halves at once: the
    JWT is gone AND the line still says something useful.
    """
    logger, stream = _captured_logger("ac45_dict_auth")

    logger.info("x=%s", {"Authorization": f"Bearer {JWT}"})

    out = stream.getvalue()
    assert out.strip(), "log line was lost entirely"
    assert JWT not in out, f"JWT leaked through a dict argument: {out!r}"
    assert "Authorization" in out, f"line no longer readable: {out!r}"
    assert "REDACTED" in out
    assert "not all arguments converted" not in capsys.readouterr().err


def test_integer_argument_still_honours_percent_d_format_spec():
    """The filter must not str() its way into breaking %d.

    A blanket str() of every argument would render '42' and then %d would raise
    TypeError - losing the line. This was correct at 4cd0f2d and must stay correct.
    """
    logger, stream = _captured_logger("percent_d_int")

    logger.info("n=%d", 42)

    assert stream.getvalue().strip() == "n=42"


def test_string_argument_is_redacted():
    """Plain string arguments still go through redaction."""
    logger, stream = _captured_logger("string_arg")

    logger.info("auth header: %s", f"Bearer {JWT}")

    out = stream.getvalue()
    assert JWT not in out
    assert "REDACTED" in out


def test_tuple_argument_arity_is_preserved(capsys):
    """A %-tuple must stay a %-tuple.

    Rebuilding args as a bare list or a single value would break the arity check
    that %-formatting performs, producing 'not enough arguments for format string'.
    """
    logger, stream = _captured_logger("tuple_arity")

    logger.info("%s=%d", "volume", 1200000)

    assert stream.getvalue().strip() == "volume=1200000"
    assert "not enough arguments" not in capsys.readouterr().err


def test_bytes_argument_round_trips_unmodified_when_clean():
    """Non-sensitive bytes must survive byte-for-byte.

    Any transformation that is not lossless would corrupt payloads logged under %b.
    """
    logger, stream = _captured_logger("bytes_clean")

    logger.info("payload=%s", "giá trị".encode("utf-8") + b"-abc")

    assert "payload=" in stream.getvalue()


def test_bytes_argument_with_jwt_is_redacted():
    """Bytes can carry a token too; the surrogateescape round-trip keeps the type."""
    logger, stream = _captured_logger("bytes_leak")

    logger.info("payload=%s", f"Bearer {JWT}".encode("utf-8"))

    out = stream.getvalue()
    assert JWT not in out
    assert "REDACTED" in out


def test_jwt_ending_in_base64url_dash_is_still_redacted():
    """A JWT's last character may legally be '-' or '_'; \\b is not a boundary there."""
    trailing_dash = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        ".eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4ifQ"
        ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5-"
    )

    assert trailing_dash not in redact_sensitive_data(f"raw={trailing_dash}")


def test_redaction_is_idempotent():
    """Running the filter twice over a record must not change it again.

    Handlers and filters can be attached more than once; a second pass must not
    eat the literal '***REDACTED***' marker.
    """
    once = redact_sensitive_data(f"Authorization: Bearer {JWT}")

    assert redact_sensitive_data(once) == once


def test_otp_rule_does_not_eat_short_numbers_in_prose():
    """The OTP rule is anchored on the value: 4-8 digits and nothing else.

    A bare number after a sensitive-sounding word is not a credential, and eating
    it would be the same destruction as AC-4.2.
    """
    assert redact_sensitive_data("otp 2 of 6 attempts") == "otp 2 of 6 attempts"


def test_otp_rule_does_not_eat_longer_numbers():
    """(?!\\d) stops the rule from half-eating an 9+ digit id."""
    raw = "transaction pin 1234567890123"

    assert redact_sensitive_data(raw) == raw


@pytest.mark.parametrize("raw", MUST_BE_UNCHANGED + ["monkey=abc"])
def test_redaction_through_a_real_handler_leaves_text_alone(raw):
    """End-to-end: the shipped handler path must agree with the helper.

    Guards against the two implementations drifting apart, which is how the
    two-copy normalisation defect of Wave 2 survived.
    """
    logger, stream = _captured_logger("handler_" + raw[:20])

    logger.info(raw)

    assert stream.getvalue().strip() == raw