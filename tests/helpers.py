"""gNMI helpers.

gNMI paths used in this project (add each new path here):
  /system/information/version
  /interface[name=<if>]/oper-state                               -> "up"
  /network-instance[name=default]/protocols/bgp/neighbor[peer-address=<ip>]/session-state
                                                                 -> "established"
  /network-instance[name=default]/protocols/ospf/instance[name=main]
      /area[area-id=0.0.0.0]/interface[interface-name=<if>.0]
      /neighbor[router-id=<id>]/adjacency-state                  -> "...:full"
"""
from pathlib import Path
from typing import Any

import yaml

INVENTORY_PATH = Path(__file__).parent / "inventory.yml"


def load_inventory() -> dict:
    """Load the expected network state from inventory.yml."""
    return yaml.safe_load(INVENTORY_PATH.read_text())


def interface_params() -> list[tuple[str, str]]:
    """(node, interface) pairs for every link interface in the inventory."""
    return [
        (node, iface.split(".")[0])
        for node, data in load_inventory()["nodes"].items()
        for iface in data["ospf_interfaces"]
    ]


def get_value(client: Any, path: str) -> Any:
    """Return the value found at a single gNMI path."""
    response = client.get(path=[path])
    updates = response["notification"][0].get("update", [])
    if not updates:
        raise LookupError(f"no data returned for path {path}")
    return updates[0]["val"]

OSPF_IFACE = (
    "/network-instance[name=default]/protocols/ospf/instance[name=main]"
    "/area[area-id=0.0.0.0]/interface[interface-name={iface}]"
)


def inventory_params(key: str) -> list[tuple[str, str]]:
    """(node, item) pairs for a list field of the inventory, e.g. 'ospf_interfaces'."""
    return [
        (node, item)
        for node, data in load_inventory()["nodes"].items()
        for item in data[key]
    ]


def get_ospf_neighbors(client: Any, iface: str) -> list[dict]:
    """Return the OSPF neighbors seen on an interface (empty list if none)."""
    try:
        value = get_value(client, OSPF_IFACE.format(iface=iface) + "/neighbor")
    except LookupError:
        return []
    return value.get("neighbor", [])

BGP_NEIGHBOR = "/network-instance[name=default]/protocols/bgp/neighbor[peer-address={peer}]"


def get_bgp_neighbor(client: Any, peer: str) -> dict:
    """Return all state of a BGP neighbor (empty dict if it isn't configured)."""
    try:
        return get_value(client, BGP_NEIGHBOR.format(peer=peer))
    except LookupError:
        return {}


def ipv4_received_routes(neighbor: dict) -> int:
    """Number of IPv4-unicast prefixes received from a BGP neighbor."""
    for afi in neighbor.get("afi-safi", []):
        if afi["afi-safi-name"].endswith("ipv4-unicast"):
            return afi.get("received-routes", 0)
    return 0

ROUTE_TABLE = "/network-instance[name=default]/route-table/ipv4-unicast/route"


def get_routes(client: Any) -> dict[str, dict]:
    """All IPv4 routes of the default network-instance, keyed by prefix."""
    try:
        value = get_value(client, ROUTE_TABLE)
    except LookupError:
        return {}
    routes: dict[str, dict] = {}
    for route in value.get("route", []):
        prefix = route["ipv4-prefix"]
        if prefix not in routes or route.get("active"):
            routes[prefix] = route
    return routes


def route_params(kind: str) -> list[tuple[str, str, str]]:
    """(node, other_node, prefix) for every router and every *other* router.

    kind is 'loopback' (the /32) or 'customer_prefix'.
    """
    nodes = load_inventory()["nodes"]
    params = []
    for node in nodes:
        for other, data in nodes.items():
            if other == node:
                continue
            prefix = f"{data['loopback']}/32" if kind == "loopback" else data["customer_prefix"]
            params.append((node, other, prefix))
    return params
