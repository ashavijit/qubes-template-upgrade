from __future__ import annotations
import json
from pathlib import Path
from unittest.mock import MagicMock, call, patch
import pytest
from template_upgrade.exceptions import AgentError, DiskSpaceError, UpgradeError, VerificationError
from template_upgrade.orchestrator import upgrade
from template_upgrade.version import find_upgrade_path

def _make_qvm_features_result(feature_name='fedora-42'):
    m = MagicMock()
    m.stdout = feature_name + '\n'
    m.returncode = 0
    return m

def _make_run_result(returncode=0, stdout='', stderr=''):
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout
    m.stderr = stderr
    return m

@pytest.fixture(autouse=True)
def patch_subprocess(tmp_path):
    with patch('subprocess.run') as mock_run, patch('subprocess.Popen') as mock_popen, patch('template_upgrade.disk.DEFAULT_CACHE_DIR', tmp_path):
        mock_run.return_value = _make_run_result(returncode=0, stdout='VERSION_ID="43"\n')
        popen_inst = MagicMock()
        popen_inst.returncode = 0
        popen_inst.wait.return_value = 0
        popen_inst.stdin = MagicMock()
        mock_popen.return_value = popen_inst
        yield (mock_run, mock_popen)

@pytest.fixture
def fedora42_info(patch_subprocess):
    mock_run, _ = patch_subprocess
    mock_run.side_effect = None

    def smart_run(cmd, **kwargs):
        cmd_str = ' '.join(cmd)
        if 'qvm-features' in cmd_str and 'template-name' in cmd_str:
            return _make_run_result(stdout='fedora-42\n')
        if 'qvm-ls' in cmd_str and '--type' in cmd_str:
            return _make_run_result(stdout='fedora-42\n')
        if 'cat /etc/os-release' in cmd_str or 'VERSION_ID' in cmd_str:
            return _make_run_result(stdout='VERSION_ID="43"\n')
        if 'rpm -qa' in cmd_str or 'dpkg-query' in cmd_str:
            return _make_run_result(stdout='bash 5.2.26\ncurl 8.0.1\n')
        return _make_run_result(returncode=0)
    mock_run.side_effect = smart_run
    return mock_run

class TestHappyPath:

    def test_fedora_single_hop_succeeds(self, fedora42_info, tmp_path):
        result = upgrade('fedora-42', target_version=43, yes=True, switch_qubes=False, print_fn=lambda _: None)
        assert result is True

    def test_upgrade_path_computed_correctly(self):
        path = find_upgrade_path('fedora', 40, 43)
        assert path == [40, 41, 42, 43]
        assert len(path) - 1 == 3

    def test_dry_run_does_nothing(self, fedora42_info):
        calls_before = fedora42_info.call_count
        upgrade('fedora-42', target_version=43, yes=True, dry_run=True, switch_qubes=False, print_fn=lambda _: None)
        calls_after = fedora42_info.call_count
        delta = calls_after - calls_before
        assert delta <= 3

    def test_user_abort_returns_false(self, fedora42_info):
        result = upgrade('fedora-42', target_version=43, yes=False, confirm_fn=lambda _: False, switch_qubes=False, print_fn=lambda _: None)
        assert result is False

class TestRollback:

    def test_rollback_called_on_agent_failure(self, patch_subprocess, tmp_path):
        mock_run, mock_popen = patch_subprocess
        popen_fail = MagicMock()
        popen_fail.returncode = 1
        popen_fail.wait.return_value = 1
        popen_fail.stdin = MagicMock()
        mock_popen.return_value = popen_fail

        def smart_run(cmd, **kwargs):
            cmd_str = ' '.join(cmd)
            if 'qvm-features' in cmd_str and 'template-name' in cmd_str:
                return _make_run_result(stdout='fedora-42\n')
            if 'cat /etc/os-release' in cmd_str or 'VERSION_ID' in cmd_str:
                return _make_run_result(stdout='VERSION_ID="42"\n')
            return _make_run_result(returncode=0)
        mock_run.side_effect = smart_run
        with pytest.raises(AgentError):
            upgrade('fedora-42', target_version=43, yes=True, switch_qubes=False, print_fn=lambda _: None)
        clone_calls = [c for c in mock_run.call_args_list if c.args and 'qvm-clone' in c.args[0]]
        assert len(clone_calls) >= 1

    def test_state_machine_recovery_action_on_agent_failure(self):
        from template_upgrade.state import StateMachine, Step
        sm = StateMachine(template='fedora-42', hop_from=42, hop_to=43)
        sm.advance(Step.CHECKPOINT_CREATED)
        sm.advance(Step.CACHE_READY)
        sm.advance(Step.AGENT_RUNNING)
        assert sm.recovery_action() == 'undo_all'

class TestVerification:

    def test_wrong_version_raises(self, patch_subprocess, tmp_path):
        mock_run, mock_popen = patch_subprocess

        def smart_run(cmd, **kwargs):
            cmd_str = ' '.join(cmd)
            if 'qvm-features' in cmd_str and 'template-name' in cmd_str:
                return _make_run_result(stdout='fedora-42\n')
            if 'VERSION_ID' in cmd_str or 'os-release' in cmd_str:
                return _make_run_result(stdout='VERSION_ID="42"\n')
            return _make_run_result(returncode=0)
        mock_run.side_effect = smart_run
        with pytest.raises((VerificationError, AgentError, UpgradeError)):
            upgrade('fedora-42', target_version=43, yes=True, switch_qubes=False, print_fn=lambda _: None)

class TestPackageDelta:

    def test_delta_computed_on_success(self, fedora42_info):
        messages = []
        upgrade('fedora-42', target_version=43, yes=True, switch_qubes=False, print_fn=messages.append)
        delta_lines = [m for m in messages if 'Package changes' in m or 'Added' in m]
        assert len(delta_lines) >= 1
