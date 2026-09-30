"""Actions ฝั่ง Windows (เจ้าของ: พีช)

ทุกฟังก์ชันคืน ActionResult เสมอ ไม่ปล่อย exception ออกไปให้ UI
signature ต้องตรงกับที่ตกลงไว้ท้าย contract.py

แนวคิด OS ที่เกี่ยวข้อง:
- Windows ไม่มี signal แบบ Unix  psutil จึงเรียก Win32 API ให้แทน
  terminate() และ kill() ต่างก็เรียก TerminateProcess -> ผลเหมือนกัน
  (Unix: SIGTERM ให้ process เก็บกวาดได้ / SIGKILL บังคับจบทันที)
- suspend/resume = หยุด/เริ่ม thread ทุกตัวของ process (Unix ใช้ SIGSTOP/SIGCONT)
- priority ของ Windows เป็น "Priority Class" ไม่ใช่ค่า nice
"""
from typing import Callable

import psutil

from contract import Action, ActionResult, Priority

# ---------- Blacklist ----------
# ชื่อเก็บเป็นตัวพิมพ์เล็ก เพื่อเทียบแบบไม่สนตัวพิมพ์เล็ก/ใหญ่
PROTECTED_NAMES = {"system", "csrss.exe", "wininit.exe", "services.exe", "lsass.exe"}
# pid 0 = System Idle Process, pid 4 = System (kernel) บน Windows
PROTECTED_PIDS = {0, 4}

# ---------- Priority mapping (DECISIONS.md D2) ----------
# ใช้ getattr เพราะค่าคงที่เหล่านี้มีเฉพาะ psutil บน Windows
# (ไฟล์นี้จะได้ import บนเครื่องอื่นได้โดยไม่ crash เช่นตอนรัน pytest บน macOS)
# ตั้งใจไม่ใช้ REALTIME_PRIORITY_CLASS: สูงกว่า thread ของระบบเอง
# ถ้า process กิน CPU เต็ม อาจทำให้เมาส์/คีย์บอร์ด/ดิสก์ไม่ตอบสนอง เครื่องค้างได้
PRIORITY_TO_CLASS: dict[str, int | None] = {
    "low": getattr(psutil, "IDLE_PRIORITY_CLASS", None),
    "below_normal": getattr(psutil, "BELOW_NORMAL_PRIORITY_CLASS", None),
    "normal": getattr(psutil, "NORMAL_PRIORITY_CLASS", None),
    "above_normal": getattr(psutil, "ABOVE_NORMAL_PRIORITY_CLASS", None),
    "high": getattr(psutil, "HIGH_PRIORITY_CLASS", None),
}


def _result(ok: bool, code, message: str, pid: int, action: Action) -> ActionResult:
    return {"ok": ok, "code": code, "message": message, "pid": pid, "action": action}


def is_protected(pid: int) -> bool:
    """True ถ้าเป็น process สำคัญของระบบที่ห้ามแตะ"""
    if pid in PROTECTED_PIDS:
        return True
    try:
        name = psutil.Process(pid).name() or ""
    except psutil.NoSuchProcess:
        return False          # ไม่มี process นี้แล้ว ให้ action ไปตอบ not_found เอง
    except (psutil.AccessDenied, Exception):
        return True           # อ่านชื่อไม่ได้ -> ถือว่าอันตรายไว้ก่อน (fail-safe)
    return name.lower() in PROTECTED_NAMES


def _protected(pid: int, action: Action) -> ActionResult:
    return _result(False, "protected", f"PID {pid} เป็น process สำคัญของระบบ ไม่อนุญาตให้ {action}", pid, action)


def _run(pid: int, action: Action, op: Callable[[psutil.Process], None], ok_msg: str) -> ActionResult:
    """ขั้นตอนกลางที่ทุก action ใช้ร่วมกัน: เช็ค blacklist -> ทำงาน -> แปลง exception เป็น error code"""
    if is_protected(pid):
        return _protected(pid, action)
    try:
        op(psutil.Process(pid))
        return _result(True, "ok", ok_msg, pid, action)
    except psutil.NoSuchProcess:       # รวม ZombieProcess ด้วย (เป็น subclass)
        return _result(False, "not_found", f"ไม่พบ PID {pid} (process อาจจบไปแล้ว)", pid, action)
    except psutil.AccessDenied:
        return _result(False, "access_denied", f"ไม่มีสิทธิ์ {action} PID {pid} (อาจต้องรันแบบ Administrator)", pid, action)
    except Exception as e:             # กันทุกกรณีที่เหลือ ห้าม exception หลุดไป UI
        return _result(False, "error", f"{action} PID {pid} ไม่สำเร็จ: {e}", pid, action)


def terminate(pid: int, confirm: bool) -> ActionResult:
    # เช็ค blacklist ก่อน confirm: process ที่ห้ามแตะ ไม่ควรถามยืนยันด้วยซ้ำ
    if is_protected(pid):
        return _protected(pid, "terminate")
    if not confirm:
        return _result(False, "needs_confirm", f"ต้องยืนยันก่อน terminate PID {pid}", pid, "terminate")
    # Windows: TerminateProcess -> process ไม่มีโอกาสเก็บกวาดเหมือน SIGTERM ของ Unix
    return _run(pid, "terminate", lambda p: p.terminate(), f"terminate PID {pid} แล้ว")


def kill(pid: int, confirm: bool) -> ActionResult:
    if is_protected(pid):
        return _protected(pid, "kill")
    if not confirm:
        return _result(False, "needs_confirm", f"ต้องยืนยันก่อน kill PID {pid}", pid, "kill")
    # บน Windows ผลเหมือน terminate() ทุกประการ (เรียก TerminateProcess เหมือนกัน)
    return _run(pid, "kill", lambda p: p.kill(), f"kill PID {pid} แล้ว")


def suspend(pid: int) -> ActionResult:
    # หยุด thread ทุกตัวของ process -> Task Manager จะแสดงสถานะ Suspended
    return _run(pid, "suspend", lambda p: p.suspend(), f"suspend PID {pid} แล้ว")


def resume(pid: int) -> ActionResult:
    return _run(pid, "resume", lambda p: p.resume(), f"resume PID {pid} แล้ว")


def set_priority(pid: int, level: Priority) -> ActionResult:
    if level not in PRIORITY_TO_CLASS:
        return _result(False, "error", f"ระดับ priority '{level}' ไม่ถูกต้อง", pid, "set_priority")
    cls = PRIORITY_TO_CLASS[level]
    if cls is None:
        return _result(False, "unsupported", "Priority Class ใช้ได้เฉพาะบน Windows", pid, "set_priority")
    # บน Windows psutil.Process.nice(value) = SetPriorityClass
    return _run(pid, "set_priority", lambda p: p.nice(cls), f"ตั้ง priority PID {pid} เป็น {level} แล้ว")
