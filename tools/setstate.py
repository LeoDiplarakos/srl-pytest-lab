import sys

from pygnmi.client import gNMIclient

host, interface, state = sys.argv[1:4]
path = f"/interface[name={interface}]/admin-state"

with gNMIclient(
    target=(host, 57400),
    username="admin",
    password="NokiaSrl1!",
    skip_verify=True,
) as gc:
    print(gc.set(update=[(path, f'"{state}"')]))
