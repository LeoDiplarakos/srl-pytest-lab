import pytest

from helpers import get_value, interface_params

PARAMS = interface_params()


@pytest.mark.parametrize("node,interface", PARAMS, ids=[f"{n}-{i}" for n, i in PARAMS])
def test_interface_oper_state_up(clients, node, interface):
    state = get_value(clients[node], f"/interface[name={interface}]/oper-state")
    assert state == "up", f"{node}: interface {interface} is {state!r}, expected 'up'"
