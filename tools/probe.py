"""Print the raw gNMI response for a path. Usage: python tools/probe.py <node-ip> <path>"""
import json
import sys

from pygnmi.client import gNMIclient

host, path = sys.argv[1], sys.argv[2]
with gNMIclient(target=(host, 57400), username="admin",
                password="NokiaSrl1!", skip_verify=True) as gc:
    print(json.dumps(gc.get(path=[path]), indent=2, default=str))
