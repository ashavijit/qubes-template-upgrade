import json
import tempfile
from pathlib import Path
import pytest
from template_upgrade.state import StateMachine, Step

@pytest.fixture
def sm():
    return StateMachine(template='fedora-42', hop_from=42, hop_to=43)

class TestAdvanceAndQuery:

    def test_initial_last_completed_is_none(self, sm):
        assert sm.last_completed() is None

    def test_advance_single_step(self, sm):
        sm.advance(Step.CHECKPOINT_CREATED)
        assert sm.last_completed() == Step.CHECKPOINT_CREATED.value

    def test_advance_preserves_order(self, sm):
        sm.advance(Step.CHECKPOINT_CREATED)
        sm.advance(Step.CACHE_READY)
        sm.advance(Step.AGENT_RUNNING)
        assert sm.last_completed() == Step.AGENT_RUNNING.value

    def test_is_complete_false_until_cleaned_up(self, sm):
        for step in list(Step)[:-1]:
            sm.advance(step)
        assert not sm.is_complete()

    def test_is_complete_true_after_cleaned_up(self, sm):
        for step in Step:
            sm.advance(step)
        assert sm.is_complete()

    def test_completed_steps_list(self, sm):
        sm.advance(Step.CHECKPOINT_CREATED)
        sm.advance(Step.CACHE_READY)
        assert sm.completed_steps() == [Step.CHECKPOINT_CREATED.value, Step.CACHE_READY.value]

class TestRecoveryAction:

    def test_nothing_started(self, sm):
        assert sm.recovery_action() == 'nothing'

    def test_checkpoint_only(self, sm):
        sm.advance(Step.CHECKPOINT_CREATED)
        assert sm.recovery_action() == 'undo_all'

    def test_cache_ready(self, sm):
        sm.advance(Step.CHECKPOINT_CREATED)
        sm.advance(Step.CACHE_READY)
        assert sm.recovery_action() == 'undo_all'

    def test_agent_succeeded(self, sm):
        for step in [Step.CHECKPOINT_CREATED, Step.CACHE_READY, Step.AGENT_RUNNING, Step.AGENT_SUCCEEDED]:
            sm.advance(step)
        assert sm.recovery_action() == 'update_features'

    def test_fully_complete(self, sm):
        for step in Step:
            sm.advance(step)
        assert sm.recovery_action() == 'nothing'

class TestPersistence:

    def test_save_and_load(self, sm, tmp_path):
        sm.advance(Step.CHECKPOINT_CREATED)
        sm.advance(Step.CACHE_READY)
        path = tmp_path / 'state.json'
        sm.save(path)
        loaded = StateMachine.load(path)
        assert loaded.template == sm.template
        assert loaded.hop_from == sm.hop_from
        assert loaded.hop_to == sm.hop_to
        assert loaded.last_completed() == sm.last_completed()

    def test_saved_file_is_valid_json(self, sm, tmp_path):
        path = tmp_path / 'state.json'
        sm.advance(Step.CHECKPOINT_CREATED)
        sm.save(path)
        data = json.loads(path.read_text())
        assert 'template' in data
        assert 'states' in data
