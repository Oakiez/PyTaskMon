import os
import signal
import subprocess
import sys
import time
import types

import psutil
import pytest

import actions_unix as a

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="Unix only")

RESULT_KEYS = {"ok", "code", "message", "pid", "action"}


@pytest.fixture
def sleeper():
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    time.sleep(0.3)
    yield p
    if p.poll() is None:
        p.kill()
    p.wait()


def _wait_until(pred, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if pred():
                return True
        except psutil.Error:
            pass
        time.sleep(0.05)
    return False


def test_is_protected_pids():
    assert a.is_protected(0) and a.is_protected(1)
    assert a.is_protected(os.getpid())


def test_is_protected_by_name(monkeypatch):
    fake = lambda pid: types.SimpleNamespace(name=lambda: "WindowServer")
    monkeypatch.setattr(a.psutil, "Process", fake)
    assert a.is_protected(424242)


def test_protected_actions_refused():
    for r in (a.kill(1, True), a.terminate(1, True), a.suspend(1),
              a.resume(1), a.set_priority(1, "low")):
        assert r["code"] == "protected" and r["ok"] is False


def test_result_shape(sleeper):
    r = a.suspend(sleeper.pid)
    assert set(r) == RESULT_KEYS
    a.resume(sleeper.pid)


def test_kill_needs_confirm(sleeper):
    for bad in (False, None, "yes", 1):
        r = a.kill(sleeper.pid, bad)
        assert r["code"] == "needs_confirm"
    assert sleeper.poll() is None            # ต้องยังไม่ตาย


def test_kill_is_sigkill(sleeper):
    r = a.kill(sleeper.pid, True)
    assert r["ok"] and r["code"] == "ok"
    assert sleeper.wait(timeout=5) == -signal.SIGKILL


def test_terminate_is_sigterm(sleeper):
    r = a.terminate(sleeper.pid, True)
    assert r["ok"]
    assert sleeper.wait(timeout=5) == -signal.SIGTERM


def test_suspend_resume(sleeper):
    assert a.suspend(sleeper.pid)["ok"]
    assert _wait_until(lambda: psutil.Process(sleeper.pid).status() == psutil.STATUS_STOPPED)
    assert a.resume(sleeper.pid)["ok"]
    assert _wait_until(lambda: psutil.Process(sleeper.pid).status() != psutil.STATUS_STOPPED)


def test_not_found():
    r = a.kill(999999, True)
    assert r["code"] == "not_found" and r["ok"] is False


def test_invalid_level(sleeper):
    for bad in ("turbo", None, 5, ["low"]):
        assert a.set_priority(sleeper.pid, bad)["code"] == "error"


def test_lower_priority_ok(sleeper):
    r = a.set_priority(sleeper.pid, "low")
    assert r["ok"]
    assert psutil.Process(sleeper.pid).nice() == 19


@pytest.mark.skipif(getattr(os, "geteuid", lambda: -1)() == 0, reason="root ลด nice ได้")
def test_raise_priority_denied_without_root(sleeper):
    a.set_priority(sleeper.pid, "low")
    r = a.set_priority(sleeper.pid, "high")
    assert r["code"] == "access_denied" and r["ok"] is False
    assert "nice" not in r["message"].lower()


def test_zombie_handled():
    p = subprocess.Popen(["true"])           # จบทันที แต่ยังไม่ wait() -> zombie
    assert _wait_until(lambda: psutil.Process(p.pid).status() == psutil.STATUS_ZOMBIE)
    r = a.kill(p.pid, True)
    assert r["ok"] is False and "zombie" in r["message"]
    p.wait()
