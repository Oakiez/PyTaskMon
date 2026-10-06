"""สาธิต zombie และ orphan process ด้วย os.fork() (Unix เท่านั้น)

วิธีใช้:
    python demo/zombie_orphan.py zombie [วินาที]
    python demo/zombie_orphan.py orphan [วินาที]

สคริปต์ยุติตัวเองเมื่อครบเวลา ไม่ทิ้ง zombie ค้างในเครื่อง
"""
import os
import sys
import time

DEFAULT_SECONDS = 60


def demo_zombie(seconds):
    pid = os.fork()
    if pid == 0:
        # โค้ดส่วนนี้รันใน "ลูก": จบทันที
        os._exit(0)

    # โค้ดส่วนนี้รันใน "พ่อ"
    print(f"พ่อ PID {os.getpid()} สร้างลูก PID {pid}", flush=True)
    print(f"ลูกจบแล้วแต่พ่อยังไม่ wait() ดังนั้นลูก PID {pid} เป็น zombie", flush=True)
    print(f"ไปดูใน dashboard ได้เลย (กรอง state = zombie) รอ {seconds} วินาที", flush=True)
    time.sleep(seconds)
    os.waitpid(pid, 0)   # พ่อเก็บกวาดลูก zombie จึงหายไป
    print("พ่อเรียก wait() แล้ว zombie หายไป", flush=True)


def demo_orphan(seconds):
    pid = os.fork()
    if pid == 0:
        # ลูก: ทำงานต่อหลังจากพ่อจบ
        print(f"ลูก PID {os.getpid()} PPID ตอนเริ่ม = {os.getppid()}", flush=True)
        time.sleep(2)   # รอให้พ่อจบก่อน
        print(f"ลูก: PPID ตอนนี้ = {os.getppid()} (ควรเป็น 1 คือ launchd)", flush=True)
        time.sleep(seconds)
        os._exit(0)     # ลูกจบเองเมื่อครบเวลา

    print(f"พ่อ PID {os.getpid()} จบก่อนลูก PID {pid} ทำให้ลูกกลายเป็น orphan", flush=True)
    os._exit(0)


def main():
    if not hasattr(os, "fork"):
        sys.exit("demo นี้ใช้ os.fork() ซึ่งมีเฉพาะ Unix (Windows ไม่รองรับ)")

    if len(sys.argv) < 2 or sys.argv[1] not in ("zombie", "orphan"):
        sys.exit("วิธีใช้: python demo/zombie_orphan.py zombie|orphan [วินาที]")

    seconds = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_SECONDS
    if sys.argv[1] == "zombie":
        demo_zombie(seconds)
    else:
        demo_orphan(seconds)


if __name__ == "__main__":
    main()