import time

from core.watchdog import ConnectionWatchdog


def test_watchdog_fires_after_consecutive_failures():
    hits = []
    wd = ConnectionWatchdog(probe=lambda: False, on_lost=lambda: hits.append(1),
                            interval_s=0.01, failures=2)
    wd.start()
    try:
        assert wd.lost.wait(1.0)
        time.sleep(0.05)
        assert hits == [1]
    finally:
        wd.stop()


def test_watchdog_resets_on_success():
    state = {"n": 0}

    def probe():
        state["n"] += 1
        return state["n"] % 2 == 0   # False, True, False, True...

    wd = ConnectionWatchdog(probe=probe, interval_s=0.01, failures=2)
    wd.start()
    try:
        time.sleep(0.2)
        assert not wd.lost.is_set()
    finally:
        wd.stop()


def test_watchdog_stop_is_idempotent():
    wd = ConnectionWatchdog(probe=lambda: True, interval_s=0.01)
    wd.start()
    wd.stop()
    wd.stop()
    assert not wd.is_running
