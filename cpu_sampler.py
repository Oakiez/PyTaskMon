import time
import psutil
from collector import get_snapshot


def run_sampler(samples=4, delay=2.0):
    cores = psutil.cpu_count(logical=True)
    print(
        f"กำลังเก็บข้อมูล CPU% จำนวน {samples} รอบ (ห่างรอบละ {delay} วินาที บน {cores} Cores)...\n"
    )

    for i in range(samples):
        snap = get_snapshot()

        # ข้ามรอบแรกเพราะค่า cpu_percent ที่คำนวณเองจะเป็น None
        if i == 0:
            time.sleep(delay)
            continue

        print(f"--- รอบที่ {i} ---")
        print(
            f"{'PID':<6} | {'NAME':<25} | {'CPU% (Ours)':<12} | {'CPU% (psutil/cores)':<15}"
        )
        print("-" * 65)

        # กรอง PID 0 ออก และเรียงตาม CPU% ของเราจากมากไปน้อย
        procs = [
            p
            for p in snap["processes"]
            if p["pid"] != 0 and p["cpu_percent"] is not None
        ]
        procs.sort(key=lambda x: x["cpu_percent"], reverse=True)

        for p in procs[:5]:
            our_cpu = f"{p['cpu_percent']:.2f}%"
            # คำนวณเทียบโดยนำ psutil_cpu หารด้วยจำนวน core เสมอ
            psutil_cpu = (
                f"{(p['cpu_percent_psutil'] / cores):.2f}%"
                if p["cpu_percent_psutil"] is not None
                else "N/A"
            )
            print(
                f"{p['pid']:<6} | {str(p['name'])[:24]:<25} | {our_cpu:<12} | {psutil_cpu:<15}"
            )

        print("\n")
        time.sleep(delay)


if __name__ == "__main__":
    run_sampler()
