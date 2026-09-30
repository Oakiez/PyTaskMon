"""PyTaskMon data contract v1.1 (อัปเดตตาราง Priority)"""

import psutil
from typing import Literal, Optional, TypedDict

CONTRACT_VERSION = "1.1"

# ---------- ค่าคงที่ที่ตกลงร่วมกัน ----------
Platform = Literal["windows", "macos"]
State = Literal[
    "running", "sleeping", "disk_sleep", "stopped", "zombie", "idle", "unknown"
]
Priority = Literal["low", "below_normal", "normal", "above_normal", "high"]
CPU_PERCENT_NORMALIZED_BY_CORES = True

# ---------- Priority Mapping (มติ D2) ----------
PRIORITY_MAP_UNIX = {
    "low": 19,
    "below_normal": 10,
    "normal": 0,
    "above_normal": -5,
    "high": -10,
}

PRIORITY_MAP_WINDOWS = {
    "low": getattr(psutil, "IDLE_PRIORITY_CLASS", 64),
    "below_normal": getattr(psutil, "BELOW_NORMAL_PRIORITY_CLASS", 16384),
    "normal": getattr(psutil, "NORMAL_PRIORITY_CLASS", 32),
    "above_normal": getattr(psutil, "ABOVE_NORMAL_PRIORITY_CLASS", 32768),
    "high": getattr(psutil, "HIGH_PRIORITY_CLASS", 128),
}


# ---------- โครงสร้างข้อมูล ----------
class ProcessInfo(TypedDict):
    pid: int
    name: Optional[str]
    ppid: Optional[int]
    state: State
    cpu_percent: Optional[float]
    cpu_percent_psutil: Optional[float]
    cpu_time_s: Optional[float]
    mem_rss: Optional[int]
    mem_vms: Optional[int]
    threads: Optional[int]
    priority: Optional[Priority]
    nice_or_priority: Optional[int]
    platform: Platform


class SystemSummary(TypedDict):
    cpu_percent: float
    cpu_cores: int
    mem_total: int
    mem_used: int
    mem_percent: float
    uptime_s: float
    process_count: int
    platform: Platform


class ProcessNode(TypedDict):
    pid: int
    children: list[int]


class Snapshot(TypedDict):
    contract_version: str
    timestamp: float
    system: SystemSummary
    processes: list[ProcessInfo]
    tree: dict[int, ProcessNode]


# ---------- Actions ----------
Action = Literal["terminate", "kill", "suspend", "resume", "set_priority"]
ErrorCode = Literal[
    "ok",
    "not_found",
    "access_denied",
    "protected",
    "needs_confirm",
    "unsupported",
    "error",
]


class ActionResult(TypedDict):
    ok: bool
    code: ErrorCode
    message: str
    pid: int
    action: Action
