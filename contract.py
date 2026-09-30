"""PyTaskMon data contract v1.0 (ตกลงร่วมกันแล้ว)

ไฟล์นี้คือ "สัญญากลาง" ระหว่าง collector (โอ๊ค), actions (พีช/โชกุน), UI (โชกุน)
แก้ไขได้ต่อเมื่อทั้ง 3 คนตกลงกันแล้วเท่านั้น และให้ bump เวอร์ชันทุกครั้ง
"""
from typing import Literal, Optional, TypedDict

CONTRACT_VERSION = "1.0"

# ---------- ค่าคงที่ที่ตกลงร่วมกัน ----------

Platform = Literal["windows", "macos"]

# state แบบ normalized (แปลงมาจาก psutil.STATUS_*)
# Windows ส่วนใหญ่จะได้แค่ running / stopped ; "zombie" มีเฉพาะ Unix
State = Literal[
    "running", "sleeping", "disk_sleep", "stopped",
    "zombie", "idle", "unknown",
]

# Priority แบบนามธรรม: UI เห็นแค่นี้ ห้ามรู้เรื่อง nice / Priority Class
Priority = Literal["low", "below_normal", "normal", "above_normal", "high"]

# ---------- สูตร CPU% (ต้องล็อกก่อนเขียนโค้ด) ----------
# มติทีม (D1 = A): cpu_percent = (delta_cpu_time / delta_wall_time) / logical_cores * 100
# -> เพดาน 100% เหมือน Task Manager ของ Windows เทียบข้าม OS ได้ตรงกัน
# (ถ้าจะเปลี่ยนเป็นแบบ top ต้องคุยกับทีม แล้วแก้ค่านี้)
CPU_PERCENT_NORMALIZED_BY_CORES = True


# ---------- โครงสร้างข้อมูล ----------

class ProcessInfo(TypedDict):
    """1 process = 1 dict ; field ใดอ่านไม่ได้ให้เป็น None (ห้าม crash)"""
    pid: int
    name: Optional[str]
    ppid: Optional[int]
    state: State
    cpu_percent: Optional[float]      # ค่าที่ collector คำนวณเอง
    cpu_percent_psutil: Optional[float]  # ค่าจาก psutil เพื่อเทียบ
    cpu_time_s: Optional[float]       # user + system (วินาที)
    mem_rss: Optional[int]            # bytes
    mem_vms: Optional[int]            # bytes
    threads: Optional[int]
    priority: Optional[Priority]      # ค่านามธรรมที่ UI ใช้
    nice_or_priority: Optional[int]   # ค่าดิบของ OS (nice / priority class) ไว้ debug/รายงาน
    platform: Platform


class SystemSummary(TypedDict):
    cpu_percent: float                # รวมทั้งระบบ 0-100
    cpu_cores: int
    mem_total: int                    # bytes
    mem_used: int                     # bytes
    mem_percent: float
    uptime_s: float
    process_count: int
    platform: Platform


class ProcessNode(TypedDict):
    """โหนดใน process tree (ใช้ pid อ้างอิง เพื่อให้ JSON ไม่ซ้อนลึกเกินไป)"""
    pid: int
    children: list[int]


class Snapshot(TypedDict):
    contract_version: str
    timestamp: float                  # time.time()
    system: SystemSummary
    processes: list[ProcessInfo]
    tree: dict[int, ProcessNode]      # key = pid


# ---------- Actions ----------

Action = Literal["terminate", "kill", "suspend", "resume", "set_priority"]

ErrorCode = Literal[
    "ok",
    "not_found",        # NoSuchProcess (process หายไปแล้ว)
    "access_denied",    # AccessDenied
    "protected",        # อยู่ใน blacklist
    "needs_confirm",    # ยังไม่ได้ confirm
    "unsupported",      # OS ไม่รองรับ action นี้
    "error",
]


class ActionResult(TypedDict):
    ok: bool
    code: ErrorCode
    message: str                      # ข้อความให้ UI แสดงตรงๆ ได้
    pid: int
    action: Action


# Signature ที่ actions.py ต้องมีทั้งสองฝั่ง OS (UI เรียกผ่านฟังก์ชันเหล่านี้เท่านั้น)
#   terminate(pid: int, confirm: bool) -> ActionResult
#   kill(pid: int, confirm: bool) -> ActionResult
#   suspend(pid: int) -> ActionResult
#   resume(pid: int) -> ActionResult
#   set_priority(pid: int, level: Priority) -> ActionResult
#   is_protected(pid: int) -> bool
