# qubes-template-upgrade

[![CI](https://github.com/ashavijit/qubes-template-upgrade/actions/workflows/ci.yml/badge.svg)](https://github.com/ashavijit/qubes-template-upgrade/actions)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org)
[![License: GPL-2.0](https://img.shields.io/badge/License-GPL--2.0-blue.svg)](LICENSE)

> One command to upgrade any Fedora or Debian template in Qubes OS.

```
qvm-template-upgrade fedora-42
qvm-template-upgrade debian-12 --target-version 13
qvm-template-upgrade upgrade-all --fedora --yes
```

Built as a GSoC 2026 proposal for [QubesOS/qubes-issues#8605](https://github.com/QubesOS/qubes-issues/issues/8605).

---

## The problem

Every Fedora template reaches end-of-life roughly once a year. The current
official procedure requires running 15–20 manual commands split across dom0
and the template terminal, in the right order. One mistake leaves a broken
template with no automatic recovery.

This tool replaces those 20 commands with one.

---

## Quick start

```bash
# Install in dom0
git clone https://github.com/ashavijit/qubes-template-upgrade
cd qubes-template-upgrade
pip install -e .

# Check your environment
qvm-template-upgrade doctor

# See what would happen (no changes made)
qvm-template-upgrade upgrade fedora-42 --dry-run

# Upgrade
qvm-template-upgrade upgrade fedora-42
```

---

## What it does

```
1. Detects distro and version from qvm-features template-name
2. Computes the shortest hop path  (e.g. fedora-40 → 41 → 42 → 43)
3. For each hop:
     a. Creates a snapshot clone  (rollback point)
     b. Allocates a 5 GB cache disk and attaches it via qvm-block
     c. Runs the agent script inside the template via qvm-run
     d. Verifies the new version by reading /etc/os-release
     e. Cleans up cache disk and removes snapshot on success
     f. On any failure: restores the snapshot automatically
4. Updates qvm-features template-name to the new version
5. Optionally re-points app qubes to the upgraded template
```

All processing runs in dom0. Nothing leaves the machine.

---

## Repository layout

```
src/template_upgrade/
  __init__.py        version, author
  cli.py             click entry point — all user-facing commands
  orchestrator.py    top-level upgrade flow, coordinates all modules
  version.py         DAG + BFS upgrade path finder
  state.py           ordered-map state machine for safe interruption
  rollback.py        snapshot stack, create/commit/restore
  retry.py           min-heap exponential-backoff scheduler
  disk.py            cache disk allocation and cleanup
  runner.py          qvm-run wrapper with timeout and output capture
  packages.py        frozenset package delta
  exceptions.py      typed exception hierarchy
  agents/
    fedora.sh        Fedora distro-sync agent (runs inside template)
    debian.sh        Debian dist-upgrade agent (runs inside template)

tests/
  unit/              fully offline — no Qubes needed
    test_version.py
    test_state.py
    test_retry.py
    test_packages.py
  integration/       subprocess-mocked pipeline tests
    test_pipeline.py
  conftest.py
```

---

## CLI reference

| Command | Description |
|---|---|
| `upgrade <template>` | Upgrade one template |
| `upgrade-all --fedora` | Upgrade all Fedora templates |
| `upgrade-all --debian` | Upgrade all Debian templates |
| `list` | Show installed templates and upgrade status |
| `doctor` | Check dom0 environment |

### Flags for `upgrade`

| Flag | Default | Description |
|---|---|---|
| `--target-version N` | auto-next | Target version number |
| `--yes / -y` | false | Skip confirmation prompts |
| `--keep-backup` | false | Keep snapshot clones after success |
| `--no-switch` | false | Do not re-point app qubes |
| `--dry-run` | false | Plan only, no changes |

---

## Running tests

```bash
pip install -e ".[dev]"

make test-unit          # 100% offline, runs anywhere
make test-integration   # subprocess mocked, runs anywhere
make test               # all tests + coverage report
make lint               # ruff
make typecheck          # mypy strict
```

---

## How rollback works

Before each upgrade hop the orchestrator clones the template:

```
fedora-42  →  fedora-42-snap-1710000000  (backup clone)
```

If the agent fails, the upgrade is interrupted, or Ctrl+C is pressed:

```
fedora-42 (broken)  →  removed
fedora-42-snap-...  →  cloned back to fedora-42
fedora-42-snap-...  →  removed
```

The user's template is restored exactly as it was before the upgrade started.
For multi-hop upgrades, one snapshot is kept per hop so partial progress
is preserved on failure.

---

## Prior art

This project builds on the community scripts from
[kennethrrosen/qubes-fedora-upgrader](https://github.com/kennethrrosen/qubes-fedora-upgrader)
and
[kennethrrosen/qubes-debian-upgrader](https://github.com/kennethrrosen/qubes-debian-upgrader),
which demonstrated the upgrade process works but lacked rollback,
integration with qvm-template, and a test suite.

---

## License

GPL-2.0 — same as Qubes OS.
