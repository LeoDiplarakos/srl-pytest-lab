import pytest

from helpers import PING_COUNT, ping, reachability_params

LOOPBACKS = reachability_params("loopback")
CUSTOMERS = reachability_params("customer")


def _ids(params):
    return [f"{node}-to-{other}" for node, other, _, _ in params]


@pytest.mark.parametrize("node,other,source,dest", LOOPBACKS, ids=_ids(LOOPBACKS))
def test_loopback_reachable(node, other, source, dest):
    received = ping(node, dest, source)
    assert received == PING_COUNT, (
        f"{node}: ping {dest} ({other} loopback) from {source}: "
        f"{received}/{PING_COUNT} replies"
    )


@pytest.mark.parametrize("node,other,source,dest", CUSTOMERS, ids=_ids(CUSTOMERS))
def test_customer_network_reachable(node, other, source, dest):
    received = ping(node, dest, source)
    assert received == PING_COUNT, (
        f"{node}: ping {dest} ({other} customer network) from {source}: "
        f"{received}/{PING_COUNT} replies"
    )
