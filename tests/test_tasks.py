import pytest

from core.tasks import TASKS, TaskProgress, TestState


def test_task_list_is_eight_steps():
    assert len(TASKS) == 8
    assert TASKS[0].kind == "preflight"
    assert [t.param for t in TASKS[3:]] == ["Ciss", "Coss", "Crss", "Rg", "Rgs"]


def test_progress_label_and_fraction():
    p = TaskProgress()
    assert p.label == "0/8 · 空闲"
    assert p.fraction == 0.0
    p.begin(2)
    assert p.label == "3/8 · 短路校准"
    assert p.fraction == pytest.approx(3 / 8)
    p.finish()
    assert p.state is TestState.DONE
    assert p.fraction == 1.0


def test_pause_resume_only_from_running():
    p = TaskProgress()
    p.pause()
    assert p.state is TestState.IDLE
    p.begin()
    p.pause()
    assert p.state is TestState.PAUSED
    p.resume()
    assert p.state is TestState.RUNNING


def test_stop_and_fail_states():
    p = TaskProgress()
    p.begin()
    p.stop()
    assert p.state is TestState.STOPPING
    p.fail()
    assert p.state is TestState.ERROR
    p.reset()
    assert p.state is TestState.IDLE
    assert p.index == 0


def test_index_is_clamped():
    p = TaskProgress()
    p.begin(99)
    assert p.index == 7
    p.set_index(-5)
    assert p.index == 0
