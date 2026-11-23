import pytest

from helpers import get_bgp_neighbor, inventory_params, ipv4_received_routes

PARAMS = inventory_params("bgp_peers")
IDS = [f"{n}-{p}" for n, p in PARAMS]


@pytest.mark.parametrize("node,peer", PARAMS, ids=IDS)
def test_bgp_session_established(clients, node, peer):
    neighbor = get_bgp_neighbor(clients[node], peer)
    state = neighbor.get("session-state", "not configured")
    assert state == "established", (
        f"{node}: BGP peer {peer} is {state!r}, expected 'established'"
    )


@pytest.mark.parametrize("node,peer", PARAMS, ids=IDS)
def test_bgp_peer_sent_prefixes(clients, node, peer):
    received = ipv4_received_routes(get_bgp_neighbor(clients[node], peer))
    assert received >= 1, (
        f"{node}: BGP peer {peer} sent {received} IPv4 prefixes, expected at least 1"
    )
