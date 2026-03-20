from __future__ import annotations
import json
import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Optional
log = logging.getLogger(__name__)

class Step(str, Enum):
    CHECKPOINT_CREATED = 'checkpoint_created'
    CACHE_READY = 'cache_ready'
    AGENT_RUNNING = 'agent_running'
    AGENT_SUCCEEDED = 'agent_succeeded'
    FEATURES_UPDATED = 'features_updated'
    CLEANED_UP = 'cleaned_up'
_RECOVERY_MAP: dict[Optional[str], str] = {None: 'nothing', Step.CHECKPOINT_CREATED.value: 'undo_all', Step.CACHE_READY.value: 'undo_all', Step.AGENT_RUNNING.value: 'undo_all', Step.AGENT_SUCCEEDED.value: 'update_features', Step.FEATURES_UPDATED.value: 'remove_backup', Step.CLEANED_UP.value: 'nothing'}

@dataclass
class StateMachine:
    template: str
    hop_from: int
    hop_to: int
    _states: dict[str, bool] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if not self._states:
            self._states = {s.value: False for s in Step}

    def advance(self, step: Step) -> None:
        if step.value not in self._states:
            raise KeyError(f'Unknown step: {step!r}')
        self._states[step.value] = True
        log.debug('State machine [%s %d→%d]: %s', self.template, self.hop_from, self.hop_to, step.value)

    def last_completed(self) -> Optional[str]:
        result: Optional[str] = None
        for step_name, done in self._states.items():
            if done:
                result = step_name
        return result

    def recovery_action(self) -> str:
        return _RECOVERY_MAP.get(self.last_completed(), 'nothing')

    def is_complete(self) -> bool:
        return self._states.get(Step.CLEANED_UP.value, False)

    def completed_steps(self) -> list[str]:
        return [s for s, done in self._states.items() if done]

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({'template': self.template, 'hop_from': self.hop_from, 'hop_to': self.hop_to, 'states': self._states}, indent=2))

    @classmethod
    def load(cls, path: str | Path) -> 'StateMachine':
        data = json.loads(Path(path).read_text())
        sm = cls(template=data['template'], hop_from=data['hop_from'], hop_to=data['hop_to'])
        sm._states = data['states']
        return sm
