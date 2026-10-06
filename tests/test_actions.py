"""Unit test ของ actions_windows.py (เจ้าของ: พีช)

กติกา: ทดสอบกับ "process จำลอง" ที่สร้างเองเท่านั้น ห้ามสั่งงาน process จริงของระบบ
และต้อง cleanup process จำลองทุกครั้ง (ทำใน fixture ส่วน finally)

รัน:  python -m pytest tests/test_actions.py -v
"""
import os
import subprocess
import sys
import time

import psutil
import pytest

# ให้ import ไฟล์ที่ root ของ repo ได้ ไม่ว่าจะรัน pytest จากโฟลเดอร์ไหน
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import actions_windows as aw  # noqa: E402

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="actions_windows ทดสอบบน Windows เท่านั้น")

# ใน venv บน Windows sys.executable เป็นแค่ launcher ที่เปิด python ตัวจริงเป็น process ลูก
# ใช้ python ตัวจริงโดยตรง เพื่อให้ action ไปโดน process ที่ทำงานจริง
PY = getattr(sys, "_base_executable", sys.executable)

RESULT_KEYS = {"ok", "code", "message", "pid", "action"}

# สคริปต์ของ process จำลอง: วน loop ไปเรื่อยๆ (sleep สั้นๆ ไม่ให้เครื่องร้อนตอนรันเทส)
DUMMY_CODE = "import time\nwhile True: time.sleep(0.05)"


@pytest.fixture
def dummy():
    """สร้าง process จำลอง แล้วเก็บกวาดให้แน่นอนหลังเทสจบ ไม่ว่าเทสจะผ่านหรือพัง"""
    proc = subprocess.Popen([PY, "-c", DUMMY_CODE])
    try:
        yield proc
    finally:
        try:
            p = psutil.Process(proc.pid)
            p.resume()          # ถ้าค้างอยู่ในสถานะ suspended ให้ปลุกก่อน
            p.kill()
        except psutil.NoSuchProcess:
            pass
        proc.wait(timeout=5)


def assert_result(res, code, action, pid):
    assert set(res) == RESULT_KEYS          # รูปแบบตรงกับ ActionResult ใน contract.py
    assert res["code"] == code
    assert res["ok"] == (code == "ok")
    assert res["action"] == action
    assert res["pid"] == pid
    assert isinstance(res["message"], str) and res["message"]


# ---------- terminate / kill ----------

def test_terminate_success(dummy):
    res = aw.terminate(dummy.pid, confirm=True)
    assert_result(res, "ok", "terminate", dummy.pid)
    assert dummy.wait(timeout=5) is not None      # process จบจริง


def test_kill_success(dummy):
    res = aw.kill(dummy.pid, confirm=True)
    assert_result(res, "ok", "kill", dummy.pid)
    assert dummy.wait(timeout=5) is not None


@pytest.mark.parametrize("func", [aw.terminate, aw.kill])
def test_needs_confirm_does_nothing(dummy, func):
    res = func(dummy.pid, confirm=False)
    assert_result(res, "needs_confirm", func.__name__, dummy.pid)
    assert psutil.pid_exists(dummy.pid) and dummy.poll() is None   # ยังไม่ถูกฆ่า


# ---------- suspend / resume ----------

def test_suspend_then_resume_changes_state(dummy):
    p = psutil.Process(dummy.pid)

    assert_result(aw.suspend(dummy.pid), "ok", "suspend", dummy.pid)
    time.sleep(0.2)
    assert p.status() == psutil.STATUS_STOPPED

    assert_result(aw.resume(dummy.pid), "ok", "resume", dummy.pid)
    time.sleep(0.2)
    assert p.status() == psutil.STATUS_RUNNING


# ---------- priority ----------

@pytest.mark.parametrize("level", ["low", "below_normal", "normal", "above_normal", "high"])
def test_set_priority_reads_back(dummy, level):
    res = aw.set_priority(dummy.pid, level)
    assert_result(res, "ok", "set_priority", dummy.pid)
    assert psutil.Process(dummy.pid).nice() == aw.PRIORITY_TO_CLASS[level]


def test_set_priority_invalid_level(dummy):
    res = aw.set_priority(dummy.pid, "realtime")
    assert_result(res, "error", "set_priority", dummy.pid)


def test_realtime_not_in_mapping():
    assert psutil.REALTIME_PRIORITY_CLASS not in aw.PRIORITY_TO_CLASS.values()


# ---------- process หายไปแล้ว ----------

def test_not_found_after_process_exit():
    proc = subprocess.Popen([PY, "-c", "pass"])
    proc.wait(timeout=5)
    pid = proc.pid
    assert_result(aw.suspend(pid), "not_found", "suspend", pid)
    assert_result(aw.resume(pid), "not_found", "resume", pid)
    assert_result(aw.set_priority(pid, "normal"), "not_found", "set_priority", pid)
    assert_result(aw.terminate(pid, confirm=True), "not_found", "terminate", pid)
    assert_result(aw.kill(pid, confirm=True), "not_found", "kill", pid)


# ---------- blacklist ----------

@pytest.mark.parametrize("pid", [0, 4])
def test_protected_system_pids(pid):
    # ถูกปฏิเสธที่ blacklist ก่อนถึง psutil จึงไม่มีการแตะ process จริง
    assert aw.is_protected(pid)
    assert_result(aw.kill(pid, confirm=True), "protected", "kill", pid)
    assert_result(aw.suspend(pid), "protected", "suspend", pid)


def test_protected_by_name_case_insensitive(dummy, monkeypatch):
    # ใส่ชื่อของ process จำลองลง blacklist ชั่วคราว (แทนการไปแตะ csrss.exe ตัวจริง)
    name = psutil.Process(dummy.pid).name()          # เช่น "python.exe"
    monkeypatch.setattr(aw, "PROTECTED_NAMES", aw.PROTECTED_NAMES | {name.lower()})
    monkeypatch.setattr(psutil.Process, "name", lambda self: name.upper())  # จำลองชื่อตัวพิมพ์ใหญ่

    assert aw.is_protected(dummy.pid)
    assert_result(aw.kill(dummy.pid, confirm=True), "protected", "kill", dummy.pid)
    assert dummy.poll() is None                      # ยังไม่ถูกฆ่า


def test_real_system_process_names_are_detected():
    # อ่านชื่ออย่างเดียว ไม่สั่งงาน: ยืนยันว่า csrss.exe ของเครื่องจริงถูกจับว่า protected
    found = [p.pid for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower() == "csrss.exe"]
    if not found:
        pytest.skip("ไม่พบ csrss.exe")
    assert all(aw.is_protected(pid) for pid in found)
