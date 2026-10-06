"""collector.py — Data Layer ของ PyTaskMon (โอ๊ค)

หน้าที่: ดึงข้อมูล process และระบบ แล้วคืนเป็น Snapshot ตาม contract.py เท่านั้น
ไม่มีการสั่งเปลี่ยนสถานะ process ใดๆ (ส่วนนั้นเป็นของ actions_*.py)

วิธีใช้:
    from collector import get_snapshot
    snap = get_snapshot()       # ครั้งแรก cpu_percent จะเป็น None (ยังไม่มีค่าก่อนหน้าไว้เทียบ)
    time.sleep(1)
    snap = get_snapshot()       # ครั้งที่สองเป็นต้นไปจึงมี cpu_percent

ทดลองรันเดี่ยวๆ:  python collector.py
"""

from __future__ import annotations

import sys
import time
import threading
from typing import Any, Callable, Optional

import psutil

from contract import (
    CONTRACT_VERSION,
    CPU_PERCENT_NORMALIZED_BY_CORES,
    PRIORITY_MAP_UNIX,
    PRIORITY_MAP_WINDOWS,
    ProcessInfo,
    ProcessNode,
    Snapshot,
    SystemSummary,
)

# ---------- Platform ----------


def detect_platform() -> str:
    """คืน "windows" / "macos" ตาม contract; OS อื่นคืน "linux" (นอกขอบเขต แต่ไม่ให้ crash)"""
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


# ---------- State ----------

_STATE_MAP = {
    psutil.STATUS_RUNNING: "running",
    psutil.STATUS_SLEEPING: "sleeping",
    psutil.STATUS_DISK_SLEEP: "disk_sleep",
    psutil.STATUS_STOPPED: "stopped",
    psutil.STATUS_ZOMBIE: "zombie",
    psutil.STATUS_IDLE: "idle",
}


def normalize_state(raw: Optional[str]) -> str:
    """แปลง psutil.STATUS_* เป็น State ใน contract; ค่าที่ไม่รู้จักเป็น "unknown" """
    if raw is None:
        return "unknown"
    return _STATE_MAP.get(raw, "unknown")


# ---------- Priority (ค่าดิบของ OS -> ระดับนามธรรม) ----------


def _windows_class_map() -> dict[int, str]:
    """คืนค่า dict สำหรับแปลง Priority Class ของ Windows กลับเป็นระดับนามธรรม"""
    return {v: k for k, v in PRIORITY_MAP_WINDOWS.items()}


def abstract_priority(raw: Optional[int], platform: str) -> Optional[str]:
    """แปลงค่าดิบ (nice / Priority Class) เป็น low..high; อ่านไม่ได้หรือไม่ตรงตาราง -> None"""
    if raw is None:
        return None
    if platform == "windows":
        return _windows_class_map().get(int(raw))
    return min(
        PRIORITY_MAP_UNIX, key=lambda level: abs(PRIORITY_MAP_UNIX[level] - int(raw))
    )


# ---------- CPU% ----------


def compute_cpu_percent(
    prev_cpu: Optional[float],
    prev_t: Optional[float],
    cur_cpu: Optional[float],
    cur_t: Optional[float],
    cores: int,
    normalize: bool = CPU_PERCENT_NORMALIZED_BY_CORES,
) -> Optional[float]:
    """สูตร: (Δcpu_time / Δwall_time) / cores × 100  (ตามมติ D1 = A)

    - ถ้าไม่มีค่าก่อนหน้า หรือเวลา/ค่าไม่สมเหตุสมผล -> None
    - normalize=True: หารด้วยจำนวน core และจำกัดไม่เกิน 100
    - normalize=False: แบบ `top` เกิน 100 ได้
    """
    if prev_cpu is None or prev_t is None or cur_cpu is None or cur_t is None:
        return None
    delta_wall = cur_t - prev_t
    delta_cpu = cur_cpu - prev_cpu
    if delta_wall <= 0 or delta_cpu < 0:
        return None
    pct = delta_cpu / delta_wall * 100.0
    if normalize:
        pct = min(pct / max(cores, 1), 100.0)
    return round(pct, 2)


# ---------- Process tree ----------


def build_tree(processes: list[ProcessInfo]) -> dict[int, ProcessNode]:
    """สร้าง pid -> {pid, children} จาก ppid

    ทุก process เป็นโหนดเสมอ; ppid ที่ไม่มี process อยู่แล้ว (orphan), ppid = None,
    หรือ ppid = pid ตัวเอง (เช่น pid 0 บน Windows) จะไม่ถูกนับเป็นลูกของใคร
    """
    pids = {p["pid"] for p in processes}
    tree: dict[int, ProcessNode] = {pid: {"pid": pid, "children": []} for pid in pids}
    for p in processes:
        ppid = p["ppid"]
        if ppid is None or ppid == p["pid"] or ppid not in pids:
            continue
        tree[ppid]["children"].append(p["pid"])
    for node in tree.values():
        node["children"].sort()
    return tree


def find_roots(processes: list[ProcessInfo]) -> list[int]:
    """pid ของ process ที่ไม่มีพ่ออยู่ในรายการ (จุดเริ่มวาดต้นไม้ใน UI)"""
    pids = {p["pid"] for p in processes}
    roots = [
        p["pid"]
        for p in processes
        if p["ppid"] is None or p["ppid"] == p["pid"] or p["ppid"] not in pids
    ]
    return sorted(roots)


# ---------- Collector ----------


class Collector:
    """เก็บ state ระหว่างการสุ่มไว้คำนวณ CPU% จึงควรสร้างครั้งเดียวแล้วเรียก collect() ซ้ำๆ"""

    def __init__(self) -> None:
        self.platform = detect_platform()
        self.cores = psutil.cpu_count(logical=True) or 1
        # (pid, create_time) -> (cpu_time_s, เวลา monotonic ตอนอ่าน)
        # ใช้ create_time ร่วมกับ pid เพราะ PID ถูกนำกลับมาใช้ซ้ำได้
        self._prev: dict[tuple[int, Optional[float]], tuple[float, float]] = {}
        # คำนวณ CPU รวมของระบบจาก cpu_times() เอง ไม่พึ่ง psutil.cpu_percent() ที่ผูกกับ thread
        self._prev_sys_times = psutil.cpu_times()
        self._last_sys_cpu = 0.0

    def collect(self) -> Snapshot:
        now_wall = time.time()
        now_mono = time.monotonic()
        processes: list[ProcessInfo] = []
        next_prev: dict[tuple[int, Optional[float]], tuple[float, float]] = {}

        for proc in psutil.process_iter():
            info = self._read_process(proc, now_mono, next_prev)
            if info is not None:
                processes.append(info)

        # ทิ้งข้อมูลของ process ที่หายไปแล้ว ไม่ให้หน่วยความจำโตเรื่อยๆ
        self._prev = next_prev
        processes.sort(key=lambda p: p["pid"])

        return {
            "contract_version": CONTRACT_VERSION,
            "timestamp": now_wall,
            "system": self._system_summary(len(processes)),
            "processes": processes,
            "tree": build_tree(processes),
        }

    # ----- internal -----

    def _read_process(
        self,
        proc: psutil.Process,
        now_mono: float,
        next_prev: dict[tuple[int, Optional[float]], tuple[float, float]],
    ) -> Optional[ProcessInfo]:
        """อ่านทุก field แบบไม่ crash; คืน None เฉพาะเมื่อ process หายไปแล้วระหว่างอ่าน"""
        gone = False
        zombie = False

        def get(fn: Callable[[], Any]) -> Any:
            nonlocal gone, zombie
            try:
                return fn()
            except psutil.ZombieProcess:
                zombie = True
            except psutil.NoSuchProcess:
                gone = True
            except psutil.AccessDenied:
                pass
            return None

        try:
            with proc.oneshot():
                create_time = get(proc.create_time)
                name = get(proc.name)
                ppid = get(proc.ppid)
                raw_status = get(proc.status)
                cpu_times = get(proc.cpu_times)
                psutil_pct = get(lambda: proc.cpu_percent(interval=None))
                mem = get(proc.memory_info)
                threads = get(proc.num_threads)
                raw_nice = get(proc.nice)
        except psutil.NoSuchProcess:
            return None

        if gone:
            return None

        state = normalize_state(raw_status)
        if state == "unknown" and zombie:
            state = "zombie"

        cpu_time_s = (cpu_times.user + cpu_times.system) if cpu_times else None

        cpu_percent = None
        if cpu_time_s is not None:
            key = (proc.pid, create_time)
            prev = self._prev.get(key)
            if prev is not None:
                cpu_percent = compute_cpu_percent(
                    prev[0], prev[1], cpu_time_s, now_mono, self.cores
                )
            next_prev[key] = (cpu_time_s, now_mono)

        nice_raw = int(raw_nice) if raw_nice is not None else None

        return {
            "pid": proc.pid,
            "name": name,
            "ppid": ppid,
            "state": state,  # type: ignore[typeddict-item]
            "cpu_percent": cpu_percent,
            "cpu_percent_psutil": psutil_pct,
            "cpu_time_s": cpu_time_s,
            "mem_rss": mem.rss if mem else None,
            "mem_vms": mem.vms if mem else None,
            "threads": threads,
            "priority": abstract_priority(nice_raw, self.platform),  # type: ignore[typeddict-item]
            "nice_or_priority": nice_raw,
            "platform": self.platform,  # type: ignore[typeddict-item]
        }

    def _system_cpu_percent(self) -> float:
        cur = psutil.cpu_times()
        prev, self._prev_sys_times = self._prev_sys_times, cur
        total = sum(cur) - sum(prev)
        if total <= 0.05:  # ช่วงสั้นเกินไป ใช้ค่าเดิม
            return self._last_sys_cpu
        idle = cur.idle - prev.idle
        pct = (1.0 - idle / total) * 100.0
        self._last_sys_cpu = round(max(0.0, min(100.0, pct)), 1)
        return self._last_sys_cpu

    def _system_summary(self, process_count: int) -> SystemSummary:
        vm = psutil.virtual_memory()
        return {
            "cpu_percent": self._system_cpu_percent(),
            "cpu_cores": self.cores,
            "mem_total": vm.total,
            "mem_used": vm.total - vm.available,
            "mem_percent": vm.percent,
            "uptime_s": time.time() - psutil.boot_time(),
            "process_count": process_count,
            "platform": self.platform,  # type: ignore[typeddict-item]
        }


# ---------- Export สำหรับ Flask (UI) ----------

_global_collector: Optional[Collector] = None
_collector_lock = threading.Lock()


def get_snapshot() -> Snapshot:
    """ฟังก์ชันหลักสำหรับให้ UI และโมดูลอื่นดึงข้อมูล (Thread-safe)"""
    global _global_collector
    with _collector_lock:
        if _global_collector is None:
            _global_collector = Collector()
        return _global_collector.collect()


# ---------- ทดลองรันเดี่ยว ----------

if __name__ == "__main__":
    get_snapshot()  # รอบแรกไว้ตั้งต้นตัวนับ
    time.sleep(1.0)
    snap = get_snapshot()

    s = snap["system"]
    print(
        f"[{s['platform']}] CPU {s['cpu_percent']}%  RAM {s['mem_percent']}%  "
        f"processes {s['process_count']}  uptime {s['uptime_s'] / 3600:.1f} h"
    )
    print(f"{'PID':>7}  {'CPU%':>6}  {'psutil%':>7}  {'STATE':<10} {'PRIO':<13} NAME")
    top = sorted(
        snap["processes"], key=lambda p: p["cpu_percent"] or 0.0, reverse=True
    )[:10]
    for p in top:
        print(
            f"{p['pid']:>7}  {p['cpu_percent'] or 0:>6}  {p['cpu_percent_psutil'] or 0:>7}  "
            f"{p['state']:<10} {str(p['priority']):<13} {p['name']}"
        )
