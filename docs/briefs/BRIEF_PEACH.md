# BRIEF — พีช (คมชาญ): Actions ฝั่ง Windows + รายงาน

> AI ผู้ช่วย: อ่าน `docs/AI_CONTEXT.md` และ `contract.py` ก่อน แล้วอ่านไฟล์นี้

- **Branch:** `feature/peach-actions`
- **ไฟล์ที่เป็นเจ้าของ:** `actions_windows.py`, `tests/test_actions.py`, `docs/report/`
- **OS ทดสอบ:** Windows
- **ต้องประสานกับ:** โชกุน (เจ้าของ `actions_unix.py`, UI) เรื่อง priority abstraction และผลทดสอบ Unix

## งานที่ต้องทำ

### 1) `actions_windows.py`

ต้องมีฟังก์ชันตาม signature ที่ตกลงไว้ใน `contract.py` (ท้ายไฟล์) และคืนค่าเป็น `ActionResult` เสมอ:

```
terminate(pid: int, confirm: bool) -> ActionResult
kill(pid: int, confirm: bool) -> ActionResult
suspend(pid: int) -> ActionResult
resume(pid: int) -> ActionResult
set_priority(pid: int, level: Priority) -> ActionResult
is_protected(pid: int) -> bool
```

- ใช้ `psutil.Process(pid)`: `.terminate()`, `.kill()`, `.suspend()`, `.resume()`, `.nice(...)`
- บน Windows `terminate()` และ `kill()` ของ psutil ให้ผลเหมือนกัน (เรียก `TerminateProcess`) ซึ่งต่างจาก Unix ที่ SIGTERM ให้ process มีโอกาสเก็บกวาดก่อน SIGKILL — **เป็นจุดเปรียบเทียบสำหรับรายงาน**
- `confirm=False` → ไม่ทำอะไร คืน `code="needs_confirm"`
- process อยู่ใน blacklist → คืน `code="protected"` (Windows: `System`, `csrss.exe`, `wininit.exe`, `services.exe`, `lsass.exe`) เทียบชื่อแบบไม่สนตัวพิมพ์เล็ก/ใหญ่ และอย่าลืมกรณี pid 0 / 4
- จับ `psutil.NoSuchProcess` → `not_found`, `psutil.AccessDenied` → `access_denied`, อื่นๆ → `error` พร้อม `message` ที่ UI แสดงได้

### 2) Priority mapping (ข้อเสนอ — ต้องยืนยันกับโชกุน)

| ระดับนามธรรม | Windows Priority Class (psutil) |
|---|---|
| `low` | `IDLE_PRIORITY_CLASS` |
| `below_normal` | `BELOW_NORMAL_PRIORITY_CLASS` |
| `normal` | `NORMAL_PRIORITY_CLASS` |
| `above_normal` | `ABOVE_NORMAL_PRIORITY_CLASS` |
| `high` | `HIGH_PRIORITY_CLASS` |

ไม่ใช้ `REALTIME_PRIORITY_CLASS` (เสี่ยงทำเครื่องค้าง) ให้ระบุเหตุผลนี้ไว้ในรายงาน

### 3) Unit test (`tests/test_actions.py`)

- ทดสอบกับ **process จำลอง** ที่สร้างเอง (เช่น `subprocess.Popen` รันสคริปต์ loop กิน CPU) ห้ามทดสอบกับ process จริงของระบบ
- ครอบคลุม: terminate สำเร็จ, suspend/resume แล้ว state เปลี่ยน, เปลี่ยน priority แล้วอ่านกลับมาตรงกัน, process หายไปแล้ว (`not_found`), pid ใน blacklist (`protected`), ไม่ confirm (`needs_confirm`)
- cleanup process จำลองทุกครั้งใน `finally` / fixture

### 4) รายงาน + สไลด์ (`docs/report/`)

- ส่วนเปรียบเทียบ Windows vs Unix: nice vs Priority Class, SIGTERM vs TerminateProcess, ชุด process state ที่ต่างกัน, zombie/orphan ที่ Windows ไม่มีแนวคิดเดียวกัน, `fork()` vs `CreateProcess`
- **ขอข้อมูลฝั่ง Unix จากโชกุน** (ผลทดสอบ nice, SIGSTOP/SIGCONT, zombie) มาใส่ให้ครบ — นัดรับข้อมูลล่วงหน้า อย่ารอวันสุดท้าย
- แนบ screenshot จาก dashboard จริงและผลรัน test

## ก่อนเริ่มเขียนโค้ด (ทำก่อน)

- [ ] คุยกับโชกุนให้ตกลง priority mapping ทั้งสองฝั่ง
- [ ] ยืนยัน signature ใน `contract.py` ว่า UI เรียกได้จริง
- [ ] ตั้ง `git config user.name` / `user.email` เป็นของตัวเองก่อน commit

## Definition of Done

- [ ] ทุกฟังก์ชันคืน `ActionResult` ไม่มี exception หลุดออกไป
- [ ] blacklist + confirm ทำงานและมี test
- [ ] test ผ่านบน Windows
- [ ] เปิด PR ให้โอ๊คหรือโชกุน review
