import pytest

from helpers import (
    get_bgp_neighbor,
    ospf_neighbor_count,
    route_next_hop_ips,
    wait_until,
)


@pytest.mark.disruptive
def test_link_failure_reroutes(clients, break_link):
    """When srl1 ethernet-1/1 (link to srl2) goes down:
    - srl1 has 1 OSPF neighbor instead of 2.
    - srl1 reaches srl2's loopback 10.0.0.2 via srl3 (next-hop 10.1.13.1).
    - The iBGP session srl1-srl2 stays Established, because it runs
      between loopbacks and OSPF finds the alternate path via srl3.
    - 192.168.2.0/24 stays in srl1's route table (BGP, next-hop 10.0.0.2).
    """
    srl1 = clients["srl1"]

    assert wait_until(lambda: ospf_neighbor_count(srl1) == 1), (
        f"expected 1 OSPF neighbor on srl1, got {ospf_neighbor_count(srl1)}"
    )

    assert wait_until(
        lambda: route_next_hop_ips(srl1, "10.0.0.2/32") == ["10.1.13.1"]
    ), f"unexpected next-hop: {route_next_hop_ips(srl1, '10.0.0.2/32')}"

    assert wait_until(
        lambda: route_next_hop_ips(srl1, "192.168.2.0/24") == ["10.0.0.2"]
    ), f"unexpected next-hop: {route_next_hop_ips(srl1, '192.168.2.0/24')}"

    assert wait_until(
        lambda: get_bgp_neighbor(srl1, "10.0.0.2")["session-state"] == "established"
    ), "iBGP session srl1-srl2 is not established"

    neighbor = get_bgp_neighbor(srl1, "10.0.0.2")
    assert neighbor["established-transitions"] == break_link["bgp_transitions"], (
        "iBGP session flapped during the failover"
    )
