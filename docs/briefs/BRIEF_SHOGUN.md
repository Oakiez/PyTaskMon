# BRIEF — โชกุน (ภีมเดช): UI + Actions ฝั่ง Unix + Zombie demo

> AI ผู้ช่วย: อ่าน `docs/AI_CONTEXT.md` และ `contract.py` ก่อน แล้วอ่านไฟล์นี้

- **Branch:** `feature/shogun-ui`
- **ไฟล์ที่เป็นเจ้าของ:** `app.py`, `ui/`, `actions_unix.py`, `demo/zombie_orphan.py`
- **OS ทดสอบ:** macOS (Apple Silicon)
- **ต้องประสานกับ:** พีช (priority mapping, ส่งผลทดสอบ Unix ให้เขียนรายงาน), โอ๊ค (รูปแบบข้อมูลจาก `collector.py`)

## งานที่ต้องทำ

### 1) Flask app + UI (`app.py`, `ui/`)

- ตาราง process แบบ auto-refresh (polling ผ่าน endpoint JSON เช่น `/api/snapshot`) ข้อมูลตามชนิด `Snapshot` ใน `contract.py`
- เรียง / ค้นหา / กรอง process ได้
- กราฟ CPU / RAM รวมของระบบ (ใช้ `SystemSummary`)
- แสดง process tree และ state ของ zombie ให้เห็นชัด
- ปุ่ม kill / suspend / resume / เปลี่ยน priority เรียกผ่าน `actions.py` เท่านั้น ห้าม import `actions_unix` หรือ `actions_windows` ตรงๆ และ UI ห้ามรู้เรื่อง nice / Priority Class
- ต้องมี **หน้าต่างยืนยัน (confirm)** ก่อน kill ทุกครั้ง และแสดง `ActionResult.message` เมื่อถูกปฏิเสธ (protected / access_denied / not_found)
- แสดง `None` เป็น "—" ห้ามให้หน้าเว็บพัง

**ความปลอดภัย:**

- รัน `app.run(host="127.0.0.1")` เท่านั้น
- endpoint ที่เปลี่ยนสถานะ process ต้องเป็น `POST` เท่านั้น
- ตรวจ `pid` ที่รับจาก client ว่าเป็นจำนวนเต็ม และฝั่ง server ต้องเช็ค blacklist/confirm เอง ห้ามเชื่อแค่ค่าจากหน้าเว็บ

### 2) `actions_unix.py`

Signature เหมือนกับฝั่ง Windows (ดู `contract.py`) คืน `ActionResult` เสมอ:

```
terminate(pid, confirm) -> ActionResult    # SIGTERM
kill(pid, confirm)      -> ActionResult    # SIGKILL
suspend(pid)            -> ActionResult    # SIGSTOP
resume(pid)             -> ActionResult    # SIGCONT
set_priority(pid, level)-> ActionResult    # nice
is_protected(pid)       -> bool
```

- Blacklist macOS: `launchd`, `kernel_task`, `WindowServer` (และ pid 0/1)
- Priority mapping ข้อเสนอ (**ต้องยืนยันกับพีช**):

| ระดับนามธรรม | nice |
|---|---|
| `low` | 19 |
| `below_normal` | 10 |
| `normal` | 0 |
| `above_normal` | -5 |
| `high` | -10 |

- **การลดค่า nice (ให้ priority สูงขึ้น) ต้องใช้สิทธิ์ root** ถ้าไม่มีสิทธิ์จะได้ `AccessDenied` → คืน `access_denied` พร้อมข้อความอธิบาย ไม่ต้องรัน dashboard ด้วย `sudo`
- บน macOS หลาย process ของระบบอ่านข้อมูลไม่ได้ถ้าไม่ใช่ root ต้องได้ `None` ไม่ crash

### 3) `demo/zombie_orphan.py`

- ใช้ `os.fork()` สาธิต **zombie** (ลูกจบแต่พ่อยังไม่ `wait()`) และ **orphan** (พ่อจบก่อนลูก แล้วลูกถูก `launchd` รับเป็นลูกบุญธรรม)
- ตรวจให้ได้ว่า state `zombie` ขึ้นใน dashboard จริง แล้วแคปภาพเก็บไว้ (ใช้ในรายงาน/สไลด์)
- ให้สคริปต์ยุติตัวเองหรือมี timeout เพื่อไม่ทิ้ง zombie ค้างในเครื่อง
- `fork()` ใช้ได้เฉพาะ Unix — เหตุผลที่ demo นี้รันบน Windows ไม่ได้ เป็นจุดเปรียบเทียบ OS ที่ควรระบุในรายงาน

### 4) ส่งมอบให้พีช (สำคัญ)

ทดสอบและบันทึกผลพฤติกรรมเฉพาะ Unix แล้วส่งให้พีชเขียนรายงาน:

- [ ] ผลของ nice ต่อ CPU% (รันสคริปต์กิน CPU 2 ตัว คนละ nice แล้วเทียบ)
- [ ] ผล SIGSTOP / SIGCONT (state เปลี่ยนเป็น `stopped` แล้วกลับ)
- [ ] ผล SIGTERM vs SIGKILL
- [ ] screenshot zombie / orphan ใน dashboard

## ก่อนเริ่มเขียนโค้ด (ทำก่อน)

- [ ] คุยกับพีชเรื่อง priority mapping
- [ ] ดู `contract.py` ให้ตรงกับที่ UI ต้องการ ถ้าขาด field ให้แจ้งโอ๊คก่อน อย่าเพิ่มเอง
- [ ] ตั้ง `git config user.name` / `user.email` เป็นของตัวเองก่อน commit

## Definition of Done

- [ ] Dashboard รันได้จริงบน macOS และแสดง `None` ได้โดยไม่พัง
- [ ] ปุ่ม action ทำงานผ่าน `actions.py`, มี confirm, แสดงข้อความ error ที่อ่านรู้เรื่อง
- [ ] zombie demo ขึ้นใน dashboard และมีภาพหลักฐาน
- [ ] ส่งผลทดสอบให้พีชแล้ว
- [ ] เปิด PR ให้โอ๊คหรือพีช review
