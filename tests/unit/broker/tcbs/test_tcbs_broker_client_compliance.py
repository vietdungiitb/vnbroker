import pytest
from unittest.mock import patch, MagicMock

from vnbroker.broker.base import BaseBrokerClient
from vnbroker.broker.tcbs.client import TCBSBrokerClient
from vnbroker.broker import BrokerRegistry, get_tcbs_broker_client
from vnbroker.common.client import Vnbroker


@pytest.mark.unit
def test_tcbs_broker_client_inheritance():
    assert issubclass(TCBSBrokerClient, BaseBrokerClient)


@pytest.mark.unit
def test_tcbs_broker_client_provider_name():
    client = TCBSBrokerClient()
    assert client.provider_name.lower() == "tcbs"
    assert client.is_authenticated is False
    client.close()


@pytest.mark.unit
def test_tcbs_broker_client_is_authenticated():
    from vnbroker.broker.session import SessionState
    client = TCBSBrokerClient()
    client.session.state = SessionState.AUTHENTICATED_READ
    assert client.is_authenticated is True


@pytest.mark.unit
def test_get_broker_client_tcbs():
    client_cls = BrokerRegistry.get("tcbs")
    assert client_cls is TCBSBrokerClient
    client = client_cls()
    assert isinstance(client, TCBSBrokerClient)


@pytest.mark.unit
def test_vnbroker_facade_broker_method():
    vn = Vnbroker()
    assert hasattr(vn, "broker")
    assert callable(vn.broker)
    client = vn.broker(provider="tcbs")
    assert isinstance(client, TCBSBrokerClient)
