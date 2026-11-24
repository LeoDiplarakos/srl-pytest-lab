"""Shared fixtures: inventory and one gNMI client per router."""
import os
from contextlib import ExitStack

import pytest
from pygnmi.client import gNMIclient

from helpers import get_routes, load_inventory

USER = os.environ.get("SRL_USER", "admin")
PASSWORD = os.environ.get("SRL_PASSWORD", "NokiaSrl1!")
PORT = int(os.environ.get("SRL_GNMI_PORT", "57400"))


@pytest.fixture(scope="session")
def inventory() -> dict:
    """Expected state of the network, loaded from inventory.yml."""
    return load_inventory()


@pytest.fixture(scope="session")
def clients(inventory):
    """One open gNMI client per node; all closed at the end of the session."""
    with ExitStack() as stack:
        yield {
            name: stack.enter_context(
                gNMIclient(
                    target=(node["host"], PORT),
                    username=USER,
                    password=PASSWORD,
                    skip_verify=True,
                    gnmi_timeout=10,
                )
            )
            for name, node in inventory["nodes"].items()
        }

@pytest.fixture(scope="module")
def route_tables(clients) -> dict:
    """Route table of every node, read once per test file."""
    return {name: get_routes(client) for name, client in clients.items()}
