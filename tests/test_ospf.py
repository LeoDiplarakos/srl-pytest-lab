import pytest

from helpers import get_ospf_neighbors, inventory_params

PARAMS = inventory_params("ospf_interfaces")


@pytest.mark.parametrize("node,iface", PARAMS, ids=[f"{n}-{i}" for n, i in PARAMS])
def test_ospf_neighbor_full(clients, node, iface):
    neighbors = get_ospf_neighbors(clients[node], iface)
    assert neighbors, f"{node}: no OSPF neighbor found on {iface}"
    for nbr in neighbors:
        state = nbr["adjacency-state"]
        assert state.endswith("full"), (
            f"{node}: OSPF neighbor {nbr['router-id']} on {iface} is {state!r}, expected 'full'"
        )
