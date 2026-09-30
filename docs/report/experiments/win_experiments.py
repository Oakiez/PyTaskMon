"""การทดลองฝั่ง Windows สำหรับรายงาน (เจ้าของ: พีช)

รันจาก root ของ repo:   python docs/report/experiments/win_experiments.py
ถ้าอยากเปิด Task Manager แคปภาพระหว่างทดลอง: เติม --pause

ใช้แต่ process จำลองที่สร้างเอง และเก็บกวาดทุกตัวก่อนจบ
"""
import os
import subprocess
import sys
import tempfile
import time

import psutil

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
import actions_windows as aw  # noqa: E402

PAUSE = "--pause" in sys.argv
# ใน venv บน Windows sys.executable เป็นแค่ launcher ที่ไปเปิด python ตัวจริงเป็น process ลูก
# ถ้าใช้ตัวนั้น เราจะตั้ง priority/suspend ผิดตัว จึงเรียก python ตัวจริงโดยตรง
PY = getattr(sys, "_base_executable", sys.executable)
HOG = "while True: pass"      # กิน CPU เต็ม 1 core


def spawn(code: str) -> subprocess.Popen:
    return subprocess.Popen([PY, "-c", code])


def cleanup(*procs):
    for pr in procs:
        try:
            psutil.Process(pr.pid).resume()
            pr.kill()
        except psutil.NoSuchProcess:
            pass
        pr.wait(timeout=5)


def cpu_s(pid: int) -> float:
    t = psutil.Process(pid).cpu_times()
    return t.user + t.system


def pause(msg: str):
    if PAUSE:
        input(f"\n>>> {msg} แล้วกด Enter เพื่อไปต่อ...")


# ---------- 1) Priority Class มีผลต่อ CPU จริงไหม ----------
def exp_priority(seconds: float = 5.0):
    print("\n=== การทดลอง 1: Priority Class (low vs high) แย่ง CPU core เดียวกัน ===")
    a, b = spawn(HOG), spawn(HOG)
    try:
        # บังคับให้อยู่ core 0 ทั้งคู่ ไม่งั้นแต่ละตัวได้ core ของตัวเอง ไม่ได้แย่งกันจริง
        for pr in (a, b):
            psutil.Process(pr.pid).cpu_affinity([0])
        print("set low :", aw.set_priority(a.pid, "low")["message"])
        print("set high:", aw.set_priority(b.pid, "high")["message"])

        start = {pr.pid: cpu_s(pr.pid) for pr in (a, b)}
        time.sleep(seconds)
        used = {pr.pid: cpu_s(pr.pid) - start[pr.pid] for pr in (a, b)}
        pause("เปิด Task Manager > Details (เพิ่มคอลัมน์ Base priority) แคปภาพ")

        print(f"\n{'PID':>7} | {'ระดับ':<6} | {'Priority Class (ค่าดิบ)':<24} | CPU time ใน {seconds:.0f}s")
        for pr, lvl in ((a, "low"), (b, "high")):
            print(f"{pr.pid:>7} | {lvl:<6} | {psutil.Process(pr.pid).nice():<24} | {used[pr.pid]:.2f} s")
    finally:
        cleanup(a, b)


# ---------- 2) suspend / resume ----------
def exp_suspend(seconds: float = 2.0):
    print("\n=== การทดลอง 2: suspend / resume ===")
    a = spawn(HOG)
    try:
        p = psutil.Process(a.pid)
        time.sleep(0.5)
        print("ก่อน suspend  :", p.status())
        aw.suspend(a.pid)
        t0 = cpu_s(a.pid)
        time.sleep(seconds)
        print("หลัง suspend  :", p.status(), f"| CPU time เพิ่ม {cpu_s(a.pid) - t0:.2f} s ใน {seconds:.0f}s")
        pause("Task Manager > Details จะเห็นสถานะ Suspended แคปภาพ")
        aw.resume(a.pid)
        t0 = cpu_s(a.pid)
        time.sleep(seconds)
        print("หลัง resume   :", p.status(), f"| CPU time เพิ่ม {cpu_s(a.pid) - t0:.2f} s ใน {seconds:.0f}s")
    finally:
        cleanup(a)


# ---------- 3) terminate vs kill ----------
# ลูกเตรียมโค้ดเก็บกวาดไว้ 2 แบบ (atexit + signal handler) ถ้าได้ทำงานจะเขียนไฟล์ marker
CLEANUP_CHILD = r"""
import atexit, signal, sys, time
marker = sys.argv[1]
def cleanup(*_):
    open(marker, "w").write("cleanup ran")
    sys.exit(0)
atexit.register(cleanup)
signal.signal(signal.SIGTERM, cleanup)
while True: time.sleep(0.05)
"""


def exp_terminate_vs_kill():
    print("\n=== การทดลอง 3: terminate vs kill (process ได้เก็บกวาดไหม) ===")
    print(f"{'action':<10} | {'exit code':<10} | ได้รันโค้ดเก็บกวาดไหม")
    for name, fn in (("terminate", aw.terminate), ("kill", aw.kill)):
        marker = os.path.join(tempfile.gettempdir(), f"pytaskmon_{name}.txt")
        if os.path.exists(marker):
            os.remove(marker)
        pr = subprocess.Popen([PY, "-c", CLEANUP_CHILD, marker])
        time.sleep(1)                         # รอให้ลูกลงทะเบียน handler เสร็จ
        fn(pr.pid, confirm=True)
        code = pr.wait(timeout=5)
        ran = os.path.exists(marker)
        print(f"{name:<10} | {code:<10} | {'ใช่' if ran else 'ไม่ได้รัน'}")
        if ran:
            os.remove(marker)


if __name__ == "__main__":
    if sys.platform != "win32":
        sys.exit("สคริปต์นี้สำหรับ Windows")
    print(f"เครื่อง: {psutil.cpu_count()} logical cores | psutil {psutil.__version__} | Python {sys.version.split()[0]}")
    exp_priority()
    exp_suspend()
    exp_terminate_vs_kill()
