"""actions_unix.py — Actions ฝั่ง Unix/macOS (เจ้าของ: โชกุน)

กฎ: ทุกฟังก์ชันคืน ActionResult (contract.py) เสมอ ไม่ raise
ห้าม import ไฟล์นี้ตรงๆ จาก UI/app.py ให้ผ่าน actions.py เท่านั้น
message ต้องไม่มีคำว่า nice เพราะ UI แสดงข้อความนี้ตรงๆ
"""
import os

import psutil

from contract import Action, ActionResult, Priority

# process สำคัญของ macOS ที่ห้ามแตะ (ตาม brief) + pid 0/1
_PROTECTED_NAMES = frozenset({"launchd", "kernel_task", "WindowServer"})
_PROTECTED_PIDS = frozenset({0, 1})

# mapping ระดับนามธรรม -> nice (มติทีม D2)
_NICE_BY_LEVEL = {
    "low": 19,
    "below_normal": 10,
    "normal": 0,
    "above_normal": -5,
    "high": -10,
}

_DENIED = "ไม่มีสิทธิ์ควบคุม process นี้ (เป็นของผู้ใช้อื่น/ระบบ) ต้องใช้สิทธิ์ root"


def _result(ok: bool, code: str, message: str, pid: int, action: Action) -> ActionResult:
    return {"ok": ok, "code": code, "message": message, "pid": pid, "action": action}


def is_protected(pid: int) -> bool:
    """True ถ้าเป็น pid 0/1, ตัว dashboard เอง หรือชื่ออยู่ใน blacklist"""
    if pid in _PROTECTED_PIDS or pid == os.getpid():
        return True
    try:
        return psutil.Process(pid).name() in _PROTECTED_NAMES
    except psutil.Error:  # NoSuchProcess / AccessDenied / ZombieProcess
        return False


def _guard(pid: int, action: Action):
    """คืน ActionResult (protected) ถ้าห้ามแตะ ไม่งั้นคืน None"""
    if pid == os.getpid():
        return _result(False, "protected",
                       "นี่คือ process ของ dashboard เอง ห้ามสั่งกับตัวเอง", pid, action)
    if is_protected(pid):
        return _result(False, "protected",
                       f"PID {pid} เป็น process สำคัญของระบบ (launchd / kernel_task / "
                       f"WindowServer) ห้ามดำเนินการ", pid, action)
    return None


def _zombie(pid: int, action: Action, ppid=None) -> ActionResult:
    parent = f" PID {ppid}" if ppid is not None else ""
    return _result(False, "error",
                   f"PID {pid} เป็น zombie (ตายแล้ว เหลือแค่ PCB รอ parent{parent} เรียก wait()) "
                   f"สั่งอะไรก็ไม่มีผล ต้องจัดการที่ parent", pid, action)


def _apply(pid: int, action: Action, fn, ok_message: str, denied_message: str) -> ActionResult:
    """ห่อ try/except ที่ทุก action ใช้ร่วมกัน"""
    try:
        proc = psutil.Process(pid)
        if proc.status() == psutil.STATUS_ZOMBIE:
            return _zombie(pid, action, proc.ppid())
        fn(proc)
        return _result(True, "ok", ok_message, pid, action)
    except psutil.ZombieProcess:          # ต้องมาก่อน NoSuchProcess (เป็นลูกของมัน)
        return _zombie(pid, action)
    except psutil.NoSuchProcess:
        return _result(False, "not_found",
                       f"PID {pid} ไม่มีอยู่แล้ว (จบการทำงานไปก่อนหน้านี้)", pid, action)
    except psutil.AccessDenied:
        return _result(False, "access_denied", denied_message, pid, action)
    except Exception as e:                # ต้องคืน ActionResult เสมอ ห้าม crash
        return _result(False, "error", f"เกิดข้อผิดพลาด: {type(e).__name__}: {e}", pid, action)


def _needs_confirm(pid: int, action: Action) -> ActionResult:
    verb = "ปิด" if action == "terminate" else "kill"
    return _result(False, "needs_confirm", f"ต้องยืนยันก่อน{verb} PID {pid}", pid, action)


def terminate(pid: int, confirm: bool) -> ActionResult:
    """SIGTERM: ขอให้ปิดตัวเอง process ดักจับได้ จึงมีโอกาส cleanup"""
    blocked = _guard(pid, "terminate")
    if blocked:
        return blocked
    if confirm is not True:
        return _needs_confirm(pid, "terminate")
    return _apply(pid, "terminate", lambda p: p.terminate(),
                  f"ส่ง SIGTERM ให้ PID {pid} แล้ว (ขอให้ปิดตัวเอง)", _DENIED)


def kill(pid: int, confirm: bool) -> ActionResult:
    """SIGKILL: kernel ฆ่าทันที ดักจับไม่ได้"""
    blocked = _guard(pid, "kill")
    if blocked:
        return blocked
    if confirm is not True:
        return _needs_confirm(pid, "kill")
    return _apply(pid, "kill", lambda p: p.kill(),
                  f"ส่ง SIGKILL ให้ PID {pid} แล้ว (บังคับปิด)", _DENIED)


def suspend(pid: int) -> ActionResult:
    """SIGSTOP: หยุด process ชั่วคราว ดักจับไม่ได้"""
    blocked = _guard(pid, "suspend")
    if blocked:
        return blocked
    return _apply(pid, "suspend", lambda p: p.suspend(),
                  f"หยุด PID {pid} ชั่วคราวแล้ว (SIGSTOP)", _DENIED)


def resume(pid: int) -> ActionResult:
    """SIGCONT: ให้ process ที่ถูกหยุดทำงานต่อ"""
    blocked = _guard(pid, "resume")
    if blocked:
        return blocked
    return _apply(pid, "resume", lambda p: p.resume(),
                  f"ให้ PID {pid} ทำงานต่อแล้ว (SIGCONT)", _DENIED)


def set_priority(pid: int, level: Priority) -> ActionResult:
    """แปลงระดับนามธรรม -> nice แล้วตั้งค่า (เพิ่ม priority ต้องใช้ root)"""
    if not isinstance(level, str) or level not in _NICE_BY_LEVEL:
        return _result(False, "error", f"ระดับ priority ไม่ถูกต้อง: {level!r}",
                       pid, "set_priority")
    blocked = _guard(pid, "set_priority")
    if blocked:
        return blocked
    value = _NICE_BY_LEVEL[level]
    return _apply(
        pid, "set_priority", lambda p: p.nice(value),
        f"เปลี่ยน priority ของ PID {pid} เป็น {level} แล้ว",
        "ไม่มีสิทธิ์: การเพิ่ม priority (above_normal / high) หรือแก้ process ของผู้ใช้อื่น "
        "ต้องใช้สิทธิ์ root — ลดเป็น low / below_normal ได้ตามปกติ",
    )
