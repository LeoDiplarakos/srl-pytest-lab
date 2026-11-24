import pytest

from helpers import route_params

LOOPBACKS = route_params("loopback")
PREFIXES = route_params("customer_prefix")


def _ids(params):
    return [f"{node}-to-{other}" for node, other, _ in params]


@pytest.mark.parametrize("node,other,prefix", LOOPBACKS, ids=_ids(LOOPBACKS))
def test_loopback_learned_via_ospf(route_tables, node, other, prefix):
    route = route_tables[node].get(prefix)
    assert route, f"{node}: no route to {other}'s loopback {prefix}"
    route_type = route["route-type"]
    assert "ospf" in route_type, (
        f"{node}: route {prefix} ({other} loopback) learned via {route_type!r}, "
        "expected OSPF"
    )


@pytest.mark.parametrize("node,other,prefix", PREFIXES, ids=_ids(PREFIXES))
def test_customer_prefix_learned_via_bgp(route_tables, node, other, prefix):
    route = route_tables[node].get(prefix)
    assert route, f"{node}: no route to {other}'s customer prefix {prefix}"
    route_type = route["route-type"]
    assert route_type.endswith("bgp"), (
        f"{node}: route {prefix} ({other} customer prefix) learned via "
        "{route_type!r}, expected BGP"
    )
    assert route["active"], f"{node}: route {prefix} is present but not active"
