# srl-pytest-lab

Automated tests for a 3-router Nokia SR Linux network (OSPF underlay + iBGP overlay),
built with Containerlab, pytest and gNMI.

[![CI](https://github.com/LeoDiplarakos/srl-pytest-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/LeoDiplarakos/srl-pytest-lab/actions/workflows/ci.yml)

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

| Layer    | What runs there                                                              |
|----------|------------------------------------------------------------------------------|
| Underlay | OSPFv2 area 0, point-to-point /31 links, `system0` loopbacks advertised (passive) |
| Overlay  | iBGP AS 65000, full mesh, sessions sourced from `system0` loopbacks          |
| Customer | Each router exports its `192.168.X.0/24` (`lo0`) into BGP via policy `EXPORT-CUSTOMER` |

Image: `ghcr.io/nokia/srlinux:26.7.2`. Topology file: `lab/srl-lab.clab.yml`,
startup configs in `lab/configs/`.

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

| File                         | What it checks                                                                     |
|------------------------------|------------------------------------------------------------------------------------|
| `tests/test_smoke.py`        | Each router answers gNMI, runs SR Linux v26.x, and its host-name matches the inventory|
| `tests/test_interfaces.py`   | Every link interface is oper-state `up`                                            |
| `tests/test_ospf.py`         | Every OSPF interface has a neighbor in state `full`                                |
| `tests/test_bgp.py`          | Every iBGP session is `established` and each peer sends at least one IPv4 prefix   |
| `tests/test_routes.py`       | Remote loopbacks are learned via OSPF; remote customer prefixes via BGP and active |
| `tests/test_reachability.py` | Ping between all loopbacks and all customer networks (every router pair)           |
| `tests/test_failover.py`     | *Disruptive:* shut srl1↔srl2 link → OSPF drops to 1 neighbor, srl2 loopback reroutes via srl3, BGP route stays, iBGP session does not flap |

Most tests are parametrized from `tests/inventory.yml`, so a failure names the exact
node, peer or interface (e.g. `test_bgp_session_established[srl1-10.0.0.2]`). The smoke
tests use a fixed node list. Shared gNMI helpers live in `tests/helpers.py`;
`tools/probe.py` prints the raw gNMI response for any path, which is handy when adding a
new test.

## CI

GitHub Actions (`.github/workflows/ci.yml`) runs on every push to `main` and on pull requests:

1. **lint** – `ruff check` and `ruff format --check`.
2. **test** – installs Containerlab on the runner, deploys the lab, runs `make wait`,
   then the safe tests and the disruptive tests as separate steps.
3. JUnit XML reports (`report-safe.xml`, `report-disruptive.xml`) are uploaded as the
   `junit-reports` artifact, and the lab is always destroyed, even if a step fails.

## Lessons / design notes
σσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσσ
- **iBGP between loopbacks, not link addresses.** Sessions are sourced from `system0`
  and the loopbacks are carried by OSPF. When a link fails, OSPF finds the path through
  the third router and the BGP session survives. The failover test checks this by
  asserting that `established-transitions` did not change.
- **`wait_until` instead of `sleep`.** Convergence time varies (especially on CI
  runners), so tests poll a condition until a timeout instead of sleeping for a fixed
  time. This makes them both faster and less flaky. `make wait` does the same at lab
  level before any test runs.
- **Disruptive tests are kept separate.** They are marked `@pytest.mark.disruptive`
  and excluded by default in `pytest.ini`, so plain `pytest` never breaks anything. The
  `break_link` fixture restores the link in a `finally` block and waits for OSPF to
  recover, so a failing test leaves the lab healthy. A killed process would not: in that
  case re-enable the interface or run `make destroy && make deploy`.
- **Expected state as data.** The inventory YAML describes what the network *should*
  look like; the parametrized tests compare it with what gNMI reports, so extending
  those checks to another router means editing YAML. The lab topology, the startup
  configs and the failover test are still router-specific.
- **Pinned management IPs.** The inventory finds routers by management IP, and Docker
  assigns IPs in container start order, which can change between runs. Early CI runs
  failed because of this. The topology now pins `mgmt-ipv4`, and a smoke test checks
  that each router's host-name matches its inventory name, so a mix-up fails with a
  clear message.

## Limitations

- The failover test covers one scenario: srl1's link to srl2 going down.
- The lab configuration is applied once as startup-config; there are no tests that push
  or roll back configuration.
- Tested with SR Linux 26.7.2 and Containerlab 0.83.0 only.
- Convergence is checked by polling with timeouts, not by measuring convergence time.
