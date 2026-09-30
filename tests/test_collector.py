"""Unit test ของ collector.py (โอ๊ค)

รันจาก root ของ repo:  pytest
ใช้ FakeProc จำลอง process เพื่อทดสอบกรณีที่สร้างจริงยาก เช่น AccessDenied / ZombieProcess
"""
import contextlib
from types import SimpleNamespace

import psutil
import pytest

import collector
from collector import (
    Collector,
    abstract_priority,
    build_tree,
    compute_cpu_percent,
    find_roots,
    normalize_state,
)
from contract import ProcessInfo, Snapshot, SystemSummary


# ---------- FakeProc ----------


class FakeProc:
    """แทน psutil.Process; ค่าใน values ถ้าเป็น Exception class จะถูก raise ตอนเรียก"""

    DEFAULTS = {
        "create_time": 1000.0,
        "name": "fake.exe",
        "ppid": 1,
        "status": psutil.STATUS_RUNNING,
        "cpu_times": SimpleNamespace(user=1.0, system=0.5),
        "cpu_percent": 0.0,
        "memory_info": SimpleNamespace(rss=1024, vms=4096),
        "num_threads": 2,
        "nice": 0,
    }

    def __init__(self, pid, **overrides):
        self.pid = pid
        self.values = {**self.DEFAULTS, **overrides}

    @contextlib.contextmanager
    def oneshot(self):
        yield

    def _get(self, key):
        value = self.values[key]
        if isinstance(value, type) and issubclass(value, Exception):
            raise value(pid=self.pid) if issubclass(value, psutil.Error) else value()
        return value

    def create_time(self): return self._get("create_time")
    def name(self): return self._get("name")
    def ppid(self): return self._get("ppid")
    def status(self): return self._get("status")
    def cpu_times(self): return self._get("cpu_times")
    def cpu_percent(self, interval=None): return self._get("cpu_percent")
    def memory_info(self): return self._get("memory_info")
    def num_threads(self): return self._get("num_threads")
    def nice(self): return self._get("nice")


def use_fake_procs(monkeypatch, procs):
    monkeypatch.setattr(collector.psutil, "process_iter", lambda *a, **k: iter(list(procs)))


# ---------- สูตร CPU% ----------


def test_cpu_percent_normalized_by_cores():
    # ใช้ CPU 1 วินาทีในเวลาจริง 2 วินาที บน 4 core -> 50% / 4 = 12.5%
    assert compute_cpu_percent(10.0, 0.0, 11.0, 2.0, cores=4, normalize=True) == 12.5


def test_cpu_percent_not_normalized_can_exceed_100():
    # แบบ top: ใช้ CPU 2 วินาทีในเวลาจริง 1 วินาที = 200%
    assert compute_cpu_percent(0.0, 0.0, 2.0, 1.0, cores=4, normalize=False) == 200.0


def test_cpu_percent_normalized_is_capped_at_100():
    assert compute_cpu_percent(0.0, 0.0, 10.0, 1.0, cores=4, normalize=True) == 100.0


@pytest.mark.parametrize(
    "args",
    [
        (None, None, 1.0, 1.0),  # ยังไม่มีค่าก่อนหน้า
        (1.0, 1.0, None, 2.0),  # อ่านค่าปัจจุบันไม่ได้
        (1.0, 1.0, 2.0, 1.0),  # Δเวลา = 0 (กันหารด้วยศูนย์)
        (5.0, 1.0, 4.0, 2.0),  # CPU time ลดลง
    ],
)
def test_cpu_percent_invalid_inputs_return_none(args):
    assert compute_cpu_percent(*args, cores=4) is None


# ---------- state / priority ----------


def test_normalize_state():
    assert normalize_state(psutil.STATUS_ZOMBIE) == "zombie"
    assert normalize_state(psutil.STATUS_STOPPED) == "stopped"
    assert normalize_state("something-new") == "unknown"
    assert normalize_state(None) == "unknown"


@pytest.mark.parametrize(
    "nice, expected",
    [(19, "low"), (15, "low"), (10, "below_normal"), (0, "normal"),
     (-5, "above_normal"), (-10, "high"), (-20, "high")],
)
def test_abstract_priority_unix_nearest(nice, expected):
    assert abstract_priority(nice, "macos") == expected


def test_abstract_priority_windows_uses_class_table(monkeypatch):
    monkeypatch.setattr(collector, "_windows_class_map", lambda: {32: "normal", 64: "low"})
    assert abstract_priority(32, "windows") == "normal"
    assert abstract_priority(64, "windows") == "low"
    assert abstract_priority(256, "windows") is None  # เช่น REALTIME ไม่อยู่ในตาราง
    assert abstract_priority(None, "windows") is None


# ---------- process tree ----------


def _p(pid, ppid):
    return {"pid": pid, "ppid": ppid}


def test_build_tree_normal_orphan_and_self_parent():
    procs = [_p(0, 0), _p(4, 0), _p(10, 4), _p(11, 4), _p(20, 999), _p(30, None)]
    tree = build_tree(procs)
    assert tree[4]["children"] == [10, 11]
    assert tree[0]["children"] == [4]  # pid 0 ที่ ppid = ตัวเอง ไม่นับเป็นลูกของตัวเอง
    assert tree[20]["children"] == []  # orphan (พ่อไม่มีอยู่) ยังเป็นโหนด
    assert set(tree) == {0, 4, 10, 11, 20, 30}
    assert find_roots(procs) == [0, 20, 30]


# ---------- collect() ทำงานจริงบนเครื่อง ----------


def test_collect_matches_contract_structure():
    snap = Collector().collect()
    assert set(snap) == set(Snapshot.__annotations__)
    assert set(snap["system"]) == set(SystemSummary.__annotations__)
    assert snap["processes"], "ควรมี process อย่างน้อย 1 ตัว"
    for p in snap["processes"]:
        assert set(p) == set(ProcessInfo.__annotations__)
    assert set(snap["tree"]) == {p["pid"] for p in snap["processes"]}


# ---------- การจัดการ exception (ใช้ FakeProc) ----------


def test_all_fields_none_when_access_denied(monkeypatch):
    denied = {k: psutil.AccessDenied for k in FakeProc.DEFAULTS}
    use_fake_procs(monkeypatch, [FakeProc(50, **denied)])
    p = Collector().collect()["processes"][0]
    assert p["pid"] == 50
    assert p["state"] == "unknown"
    for field in ("name", "ppid", "cpu_percent", "cpu_percent_psutil", "cpu_time_s",
                  "mem_rss", "mem_vms", "threads", "priority", "nice_or_priority"):
        assert p[field] is None, field


def test_zombie_process_is_reported_as_zombie(monkeypatch):
    zombie = {"status": psutil.ZombieProcess, "name": psutil.ZombieProcess,
              "cpu_times": psutil.ZombieProcess, "memory_info": psutil.ZombieProcess}
    use_fake_procs(monkeypatch, [FakeProc(60, **zombie)])
    p = Collector().collect()["processes"][0]
    assert p["state"] == "zombie"
    assert p["name"] is None and p["mem_rss"] is None


def test_process_that_vanished_is_skipped(monkeypatch):
    use_fake_procs(monkeypatch, [FakeProc(70, create_time=psutil.NoSuchProcess), FakeProc(71)])
    pids = [p["pid"] for p in Collector().collect()["processes"]]
    assert pids == [71]


# ---------- CPU% ข้ามการสุ่มสองรอบ ----------


def test_cpu_percent_needs_two_samples_and_pid_reuse_is_not_mixed(monkeypatch):
    c = Collector()
    c.cores = 1
    clock = iter([100.0, 101.0, 102.0])
    monkeypatch.setattr(collector.time, "monotonic", lambda: next(clock))

    def times(user):
        return SimpleNamespace(user=user, system=0.0)

    # รอบ 1: ยังไม่มีค่าก่อนหน้า -> None
    use_fake_procs(monkeypatch, [FakeProc(80, cpu_times=times(1.0))])
    assert c.collect()["processes"][0]["cpu_percent"] is None

    # รอบ 2: process เดิม ใช้ CPU เพิ่ม 0.5 วินาทีใน 1 วินาที -> 50%
    use_fake_procs(monkeypatch, [FakeProc(80, cpu_times=times(1.5))])
    assert c.collect()["processes"][0]["cpu_percent"] == 50.0

    # รอบ 3: PID เดิมแต่ create_time ต่าง (คนละ process) -> ต้องไม่เอามาคำนวณปนกัน
    use_fake_procs(monkeypatch, [FakeProc(80, create_time=5555.0, cpu_times=times(99.0))])
    assert c.collect()["processes"][0]["cpu_percent"] is None
