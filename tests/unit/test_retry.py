import time
from unittest.mock import patch
import pytest
from template_upgrade.retry import RetryScheduler

@pytest.fixture
def sched():
    return RetryScheduler(base=0.01, cap=0.1, max_attempts=3)

class TestScheduleAndPoll:

    def test_nothing_ready_immediately(self, sched):
        sched.schedule('task', attempt=0)
        assert sched.next_ready() is None

    def test_ready_after_delay(self, sched):
        sched.schedule('task', attempt=0)
        time.sleep(0.02)
        result = sched.next_ready()
        assert result is not None
        assert result[0] == 'task'
        assert result[1] == 0

    def test_heap_empty_after_pop(self, sched):
        sched.schedule('task', attempt=0)
        time.sleep(0.02)
        sched.next_ready()
        assert sched.is_empty()

    def test_multiple_tasks_ordered_by_time(self, sched):
        sched.schedule('a', attempt=2)
        sched.schedule('b', attempt=0)
        time.sleep(0.15)
        first = sched.next_ready()
        second = sched.next_ready()
        assert first[0] == 'b'
        assert second[0] == 'a'

class TestBackoffDelays:

    def test_delay_doubles_each_attempt(self):
        sched = RetryScheduler(base=2.0, cap=60.0)
        delays = [min(2.0 ** i, 60.0) for i in range(5)]
        assert delays == [1.0, 2.0, 4.0, 8.0, 16.0]

    def test_delay_capped(self):
        sched = RetryScheduler(base=2.0, cap=5.0)
        delay = min(2.0 ** 10, 5.0)
        assert delay == 5.0

class TestBudget:

    def test_within_budget(self, sched):
        assert sched.has_budget(0)
        assert sched.has_budget(2)

    def test_budget_exhausted(self, sched):
        assert not sched.has_budget(3)
        assert not sched.has_budget(10)

class TestSecondsUntilNext:

    def test_none_when_empty(self, sched):
        assert sched.seconds_until_next() is None

    def test_positive_when_scheduled(self, sched):
        sched.schedule('task', attempt=2)
        wait = sched.seconds_until_next()
        assert wait is not None
        assert wait > 0
