import builtins
import pytest

from vnbroker.core.exceptions import (
    vnbrokerDeprecationWarning,
    DeprecationWarning as AliasedWarning,
)


@pytest.mark.unit
def test_vnbroker_deprecation_warning():
    assert issubclass(vnbrokerDeprecationWarning, UserWarning)
    assert AliasedWarning is vnbrokerDeprecationWarning


@pytest.mark.unit
def test_builtin_deprecation_warning_not_overwritten():
    assert builtins.DeprecationWarning is not vnbrokerDeprecationWarning
    assert issubclass(builtins.DeprecationWarning, Warning)
