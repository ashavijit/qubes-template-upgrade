from __future__ import annotations
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from template_upgrade.packages import Package
from template_upgrade.state import StateMachine, Step
from template_upgrade.rollback import RollbackManager
from template_upgrade.retry import RetryScheduler

@pytest.fixture
def fedora42_name() -> str:
    return 'fedora-42'

@pytest.fixture
def debian12_name() -> str:
    return 'debian-12'

@pytest.fixture
def fresh_sm(fedora42_name) -> StateMachine:
    return StateMachine(template=fedora42_name, hop_from=42, hop_to=43)

@pytest.fixture
def mid_upgrade_sm(fresh_sm) -> StateMachine:
    fresh_sm.advance(Step.CHECKPOINT_CREATED)
    fresh_sm.advance(Step.CACHE_READY)
    fresh_sm.advance(Step.AGENT_RUNNING)
    return fresh_sm

@pytest.fixture
def complete_sm(fresh_sm) -> StateMachine:
    for step in Step:
        fresh_sm.advance(step)
    return fresh_sm

def _pkg(name: str, ver: str) -> Package:
    return Package(name=name, version=ver)

@pytest.fixture
def packages_before() -> frozenset[Package]:
    return frozenset([_pkg('bash', '5.1.16'), _pkg('curl', '7.88.1'), _pkg('python3', '3.11.2'), _pkg('old-lib', '1.0.0')])

@pytest.fixture
def packages_after() -> frozenset[Package]:
    return frozenset([_pkg('bash', '5.2.26'), _pkg('curl', '8.0.1'), _pkg('python3', '3.12.0'), _pkg('new-lib', '2.0.0')])

def make_run_result(returncode: int=0, stdout: str='', stderr: str='') -> MagicMock:
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout
    m.stderr = stderr
    return m
