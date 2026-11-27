# srl-pytest-lab

I built this lab to learn how network automation and testing work in practice: a small
Nokia SR Linux network that I deploy as code, test automatically over gNMI, and break on
purpose to see how it recovers.

[![CI](https://github.com/LeoDiplarakos/srl-pytest-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/LeoDiplarakos/srl-pytest-lab/actions/workflows/ci.yml)

## Why I built it

My diploma thesis was about an orchestrator that provisions L3VPN transport slices through
an SDN controller. There, the controller configured the network for me. I wanted to go one
layer lower: configure the routing protocols myself, and prove with tests that the network
behaves the way I expect. My goals were to:

- run a real router OS locally, with Containerlab and Nokia SR Linux;
- describe the expected state of the network as data and check it automatically;
- break a link on purpose, check that traffic reroutes, and measure how long it takes;
- run everything in CI, so a fresh machine can reproduce it.

## What it does

The test suite reads live state from every router over gNMI and checks it against an
expected-state inventory (`tests/inventory.yml`). It covers interfaces, OSPF adjacencies,
iBGP sessions and route tables. End-to-end ping between loopbacks and customer networks
runs `ping` inside the router containers via `docker exec`. A separate **disruptive**
failover test shuts down a link, checks that traffic reroutes without the iBGP session
flapping, and then restores the link.

## Topology

```
                    AS 65000 (iBGP full mesh between loopbacks)

                 ┌──────────────────────┐
                 │         srl1         │
                 │  system0 10.0.0.1/32 │
                 │  lo0  192.168.1.1/24 │
                 └──────────────────────┘
          e1-1 10.1.12.0/31        e1-2 10.1.13.0/31
                 /                          \
                /                            \
   e1-1 10.1.12.1/31                     e1-2 10.1.13.1/31
 ┌──────────────────────┐            ┌──────────────────────┐
 │         srl2         │            │         srl3         │
 │  system0 10.0.0.2/32 │────────────│  system0 10.0.0.3/32 │
 │  lo0  192.168.2.1/24 │            │  lo0  192.168.3.1/24 │
 └──────────────────────┘            └──────────────────────┘
      e1-2 10.1.23.0/31                 e1-1 10.1.23.1/31
```

| Layer    | What runs there                                                                        |
|----------|----------------------------------------------------------------------------------------|
| Underlay | OSPFv2 area 0, point-to-point /31 links, `system0` loopbacks advertised (passive)      |
| Overlay  | iBGP AS 65000, full mesh, sessions sourced from `system0` loopbacks                    |
| Customer | Each router exports its `192.168.X.0/24` (`lo0`) into BGP via policy `EXPORT-CUSTOMER` |

I chose a triangle on purpose: every router has a direct link and a detour through the
third router, so a single link failure is survivable and testable.

Image: `ghcr.io/nokia/srlinux:26.7.2`. Topology file: `lab/srl-lab.clab.yml`, startup
configs in `lab/configs/`.

## What I measured

To see the failover from the traffic's point of view, I ran a ping every 100 ms from
srl1's loopback to srl2's loopback while shutting the srl1–srl2 link, three times:

| Run | Packets lost when the link went down | Outage  | Packets lost when it came back |
|-----|--------------------------------------|---------|--------------------------------|
| 1   | 11                                   | ~1.1 s  | not captured                   |
| 2   | 10                                   | ~1.0 s  | not captured                   |
| 3   | 9                                    | ~0.9 s  | 0                              |

The TTL of the replies dropped from 64 to 63 after the failure: traffic was now taking the
extra hop through srl3. Recovery lost nothing, because OSPF brings the direct adjacency
back to full before moving the route, so the detour keeps working until the direct path is
ready.

About one second is close to a best case: an administrative shutdown is detected
instantly. A real fibre cut that doesn't drop the link would depend on the OSPF dead
interval, unless BFD is used.

## Quick start

Requirements: Docker, [Containerlab](https://containerlab.dev), Python 3.12, and `sudo`
rights (Containerlab needs them to deploy and destroy the lab). The tests must run on the
same host as Docker, because the ping tests use `docker exec`.

```bash
pip install -r requirements.txt

make deploy            # start the 3-router lab with Containerlab
make wait              # poll until OSPF + BGP have converged
make test              # run all safe (read-only) tests
make test-disruptive   # run the link-failover test
make destroy           # tear the lab down
```

Other targets: `make lint`, `make format` (ruff), `make test-all` (safe + disruptive).

gNMI credentials can be overridden with `SRL_USER`, `SRL_PASSWORD` and `SRL_GNMI_PORT`.

## Tests

The test files follow the layers of the network, so when something breaks, the first
layer that fails points to the cause.

| File                         | What it checks                                                                         |
|------------------------------|----------------------------------------------------------------------------------------|
| `tests/test_smoke.py`        | Each router answers gNMI, runs SR Linux v26.x, and its host-name matches the inventory |
| `tests/test_interfaces.py`   | Every link interface is oper-state `up`                                                |
| `tests/test_ospf.py`         | Every OSPF interface has a neighbor in state `full`                                    |
| `tests/test_bgp.py`          | Every iBGP session is `established` and each peer sends at least one IPv4 prefix       |
| `tests/test_routes.py`       | Remote loopbacks are learned via OSPF; remote customer prefixes via BGP and active     |
| `tests/test_reachability.py` | Ping between all loopbacks and all customer networks (every router pair)               |
| `tests/test_failover.py`     | *Disruptive:* shut srl1↔srl2 link → OSPF drops to 1 neighbor, srl2 loopback reroutes via srl3, BGP route stays, iBGP session does not flap |

Most tests are parametrized from `tests/inventory.yml`, so a failure names the exact node,
peer or interface (e.g. `test_bgp_session_established[srl1-10.0.0.2]`). The smoke tests
use a fixed node list. Shared gNMI helpers live in `tests/helpers.py`; `tools/probe.py`
prints the raw gNMI response for any path, which is how I found the paths for each test.

To make sure the tests actually catch problems, I broke the network on purpose (disabled a
BGP neighbor, removed an export policy, shut an interface), predicted which tests should
fail, and checked that exactly those failed.

## CI

GitHub Actions (`.github/workflows/ci.yml`) runs on every push to `main` and on pull
requests:

1. **lint**: `ruff check` and `ruff format --check`.
2. **test**: installs Containerlab on the runner, deploys the lab, runs `make wait`, then
   the safe tests and the disruptive tests as separate steps.
3. JUnit XML reports are uploaded as an artifact, and the lab is always destroyed, even if
   a step fails.

## Problems I ran into

Most of what I learned came from things that went wrong:

- **A routing policy without a `match` statement.** It was committed with a syntax error
  in the match line, so the policy matched everything. I now run `diff` before every
  `commit`.
- **Customer prefixes in OSPF.** OSPF (preference 10) beat iBGP (170), so the BGP routes
  stayed inactive. Each protocol now carries one kind of route: OSPF the infrastructure,
  BGP the customer prefixes.
- **A router configured as its own BGP neighbor.** I found it by diffing the three config
  files against each other.
- **A wait helper that hid a bug.** My first `wait_until` caught every exception, so a
  `NameError` in my own code looked like a 60-second network timeout. It now catches only
  the errors that mean "not ready yet".
- **A typo that disabled a safety net.** `-m "not distruptive"` matched no tests, so the
  failover test still ran in the default suite. I noticed because the output didn't say
  `1 deselected`.
- **Tests that started too early in CI.** The first CI run failed because BGP hadn't
  converged yet. `make wait` now polls until OSPF is full and BGP is established.
- **A flaky CI run.** It passed, then failed on a re-run with the same code. The deploy
  log showed that Docker had assigned the management IPs in a different order, so the
  test for srl1 was talking to srl3. The topology now pins `mgmt-ipv4`, and a smoke test
  checks each router's host-name against the inventory.

## Design notes

- **iBGP between loopbacks, not link addresses.** When a link fails, OSPF finds the path
  through the third router and the BGP session survives. The failover test checks this by
  asserting that the `established-transitions` counter did not change.
- **Polling instead of `sleep`.** Convergence time varies, especially on CI runners, so
  tests wait for a condition with a timeout instead of sleeping for a fixed time.
- **Disruptive tests are kept separate.** They are excluded by default in `pytest.ini`, so
  plain `pytest` never breaks anything. The `break_link` fixture restores the link in a
  `finally` block and waits for OSPF to recover. A killed process would not restore it: in
  that case re-enable the interface or run `make destroy && make deploy`.
- **Expected state as data.** The inventory describes what the network *should* look
  like; the parametrized tests compare it with what gNMI reports. The lab topology, the
  startup configs and the failover test are still router-specific.

## Limitations

- The failover test covers one scenario: srl1's link to srl2 going down.
- The lab configuration is applied once as startup-config; there are no tests that push
  or roll back configuration.
- Tested with SR Linux 26.7.2 and Containerlab 0.83.0 only.
- The outage was measured by hand with ping; the failover test itself checks convergence
  but does not time it.

## What I'd like to add next

- Measure the outage automatically inside the failover test.
- Enable BFD and compare failure detection with and without it.
- Replace polling with gNMI Subscribe (streaming telemetry).
- Add tests that push a configuration change, verify it and roll it back.