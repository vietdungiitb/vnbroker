"""Failover parity between the single-symbol router and the bulk router.

`bulk_router.PROVIDER_ERRORS` lists `OSError`, which covers the whole requests
and socket failure family:

    requests.exceptions.RequestException -> IOError -> OSError
    socket.gaierror (DNS)                -> OSError
    ssl.SSLError                         -> OSError

`source_router.should_failover` did NOT, so a DNS failure or connection reset
aborted the single-symbol path while the bulk path kept going. Same provider,
same outage, two different answers.
"""
from __future__ import annotations

import socket
import ssl

import pytest
import requests

from vnbroker.core.bulk_router import PROVIDER_ERRORS
from vnbroker.core.source_router import should_failover

NETWORK_ERRORS = [
    ConnectionError("refused"),
    TimeoutError("timed out"),
    socket.gaierror("Name or service not known"),
    ssl.SSLError("handshake failure"),
    ConnectionResetError("reset by peer"),
    requests.exceptions.ConnectionError("failed to establish a new connection"),
    requests.exceptions.Timeout("read timed out"),
    requests.exceptions.SSLError("bad handshake"),
]


@pytest.mark.parametrize("exc", NETWORK_ERRORS, ids=lambda e: type(e).__name__)
def test_network_error_triggers_failover(exc):
    assert should_failover(exc) is True


def test_requests_family_is_not_special_cased():
    """Guards the actual defect: it is enough to be an OSError.

    A custom requests exception whose message carries no marker word must still
    fail over - previously it fell through to the string check and returned
    False."""
    bare = requests.exceptions.RequestException("boom")
    assert not any(m in "boom" for m in ("429", "403", "timeout", "connection"))
    assert should_failover(bare) is True


def test_bulk_and_single_router_agree_on_the_network_family():
    """The parity assertion itself - both routers, same exception list."""
    for exc in NETWORK_ERRORS:
        assert isinstance(exc, PROVIDER_ERRORS) is True, (
            f"{type(exc).__name__} is not in PROVIDER_ERRORS but "
            "should_failover accepts it - the routers drifted again"
        )
        assert should_failover(exc) is True


PROGRAMMING_ERRORS = [
    TypeError("bad operand"),
    ValueError("not a number"),
    AttributeError("'NoneType' object has no attribute 'close'"),
    ZeroDivisionError("division by zero"),
    NameError("name 'x' is not defined"),
]


@pytest.mark.parametrize("exc", PROGRAMMING_ERRORS, ids=lambda e: type(e).__name__)
def test_programming_errors_still_propagate(exc):
    """Widening to OSError must not turn a real bug into a silent failover."""
    assert should_failover(exc) is False


def test_existing_marker_behaviour_is_preserved():
    for message in ("HTTP 429 Too Many Requests", "HTTP 403 Forbidden",
                    "rate limit reached", "service unavailable"):
        assert should_failover(RuntimeError(message)) is True
    assert should_failover(RuntimeError("nothing recognisable")) is False