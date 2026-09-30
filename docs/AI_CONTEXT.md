# PyTaskMon — บริบทโปรเจกต์ (สำหรับ AI ผู้ช่วย)

> ไฟล์นี้ให้ AI ผู้ช่วยของสมาชิกทีมอ่านก่อนเริ่มช่วยงาน อ่านคู่กับ `contract.py` และไฟล์ `BRIEF_*.md` ของเจ้าของงาน
> ภาษาที่ใช้คุยกับสมาชิก: ไทย (ชื่อฟังก์ชัน/โค้ด/คอมเมนต์เทคนิคเป็นอังกฤษได้)

## 1. โปรเจกต์คืออะไร

PyTaskMon คือเครื่องมือ Web-based (Flask) สำหรับ monitor และควบคุม process บน **Windows และ macOS** ใช้ `psutil`
เป็นโปรเจกต์วิชา Operating Systems เพื่อศึกษา PCB, process state, CPU utilization, signal, priority และเปรียบเทียบกลไก Windows vs Unix

- Repo: https://github.com/Oakiez/PyTaskMon
- Python 3.12 หรือ 3.13 (ทั้งทีมต้องตรงกัน), library หลัก: `psutil`, `Flask`
- วันพรีเซนต์: 7 ตุลาคม 2569
- ทีม: โอ๊ค (วงศธร), โชกุน (ภีมเดช), พีช (คมชาญ)

## 2. ขอบเขต

**ทำ:** รายการ process แบบ PCB (pid, ppid, state, priority, CPU time, RSS/VMS, threads), คำนวณ CPU% เอง เทียบกับ psutil, process tree, สาธิต zombie/orphan (macOS เท่านั้น เพราะ `os.fork()`), kill / suspend / resume / ปรับ priority, สรุปข้อมูลระบบ (CPU, RAM, uptime), dashboard เรียง/ค้นหา/กรองได้

**ไม่ทำ:** kernel module, Linux อย่างเป็นทางการ, TUI/curses, การเข้าถึงจากเครื่องอื่น (bind `127.0.0.1` เท่านั้น เพราะมีปุ่ม kill), การรับประกัน field ที่ OS ไม่รองรับ (ใช้ `None` / "—")

## 3. สถาปัตยกรรมและเจ้าของไฟล์

```
collector.py          โอ๊ค    Data Layer
actions.py            (ตัวเลือกตาม sys.platform ให้ import ฝั่งที่ตรงกับ OS)
actions_windows.py    พีช     Actions ฝั่ง Windows
actions_unix.py       โชกุน   Actions ฝั่ง Unix
contract.py           ทุกคน   data contract (แก้ต้องแจ้งทีมก่อน)
app.py, ui/           โชกุน   Flask + หน้าเว็บ
demo/zombie_orphan.py โชกุน   demo zombie/orphan
tests/                โอ๊ค (test_collector) / พีช (test_actions)
docs/report/          พีช     รายงาน + สไลด์
```

> หมายเหตุ: ต่างจากเอกสาร handover ต้นฉบับ ที่ให้ `actions.py` ไฟล์เดียว สองคนแก้ ตอนนี้แยกเป็น `actions_windows.py` / `actions_unix.py` เพื่อลด merge conflict

## 4. กฎที่ต้องยึด (ห้ามฝ่าฝืนเมื่อเสนอโค้ด)

1. **ยึด `contract.py` เป็นความจริงเดียว** ชื่อ field, ชนิดข้อมูล, `State`, `Priority`, `ActionResult` ห้ามคิดชื่อใหม่เอง ถ้าคิดว่าต้องแก้ ให้บอกสมาชิกว่าต้องคุยกับทีมก่อน
2. **Priority ต้องเป็นนามธรรม** UI เห็นแค่ `low / below_normal / normal / above_normal / high` การแปลงเป็น nice (Unix) หรือ Priority Class (Windows) อยู่ใน `actions_*.py` เท่านั้น UI ห้ามรู้เรื่อง OS
3. **ทุก field ต้องเป็น `None` ได้** ห้าม crash เพราะอ่านค่าไม่ได้
4. **จับ exception ของ psutil เสมอ:** `psutil.AccessDenied`, `psutil.NoSuchProcess`, `psutil.ZombieProcess` แล้วแปลงเป็น `None` หรือ `ActionResult` ที่มี error code
5. **ห้าม kill process สำคัญ** blacklist — Windows: `System`, `csrss.exe`, `wininit.exe`, `services.exe`, `lsass.exe`; macOS: `launchd`, `kernel_task`, `WindowServer` และต้อง confirm ก่อน kill ทุกครั้ง
6. **Server bind `127.0.0.1` เท่านั้น** และ action ที่เปลี่ยนสถานะ process ต้องเป็น `POST` เท่านั้น (ห้ามเป็น `GET`)
7. **CPU%:** ข้อเสนอปัจจุบัน = (delta CPU time / delta เวลาจริง) / จำนวน logical core × 100 (เพดาน 100%) — *ยังรอทีมยืนยัน*

## 5. กฎ Git (อาจารย์กำชับ)

- ห้าม push ตรงเข้า `main` ทำงานใน branch ของตัวเอง แล้วเปิด Pull Request ให้ **อีกอย่างน้อย 1 คน** review ก่อน merge
- Branch: `feature/oak-collector`, `feature/peach-actions`, `feature/shogun-ui`
- Commit message: `[ส่วนงาน] คำอธิบาย (ชื่อ)` เช่น `[actions] implement suspend for Windows (Peach)`
- push สม่ำเสมอ อย่างน้อยสัปดาห์ละ 2-3 ครั้ง ห้าม force-push เข้า `main` ห้าม commit secret/`.env`
- ทุกคนต้องเขียนและ commit งานของตัวเองจริง (ห้ามให้คนเดียว push แทนทุกคน)

## 6. แนวทางสำหรับ AI ผู้ช่วย

- สมาชิกต้อง **เข้าใจและอธิบายโค้ดของตัวเองได้ตอนพรีเซนต์** ให้อธิบายเหตุผลของโค้ดและแนวคิด OS ที่เกี่ยวข้องควบคู่กับโค้ดเสมอ อย่าโยนโค้ดยาวโดยไม่อธิบาย
- แก้เฉพาะไฟล์ที่เป็นของสมาชิกคนนั้น ถ้าต้องแตะไฟล์ของคนอื่นหรือ `contract.py` ให้เตือนว่าต้องคุยกับเจ้าของก่อน
- ถ้าไม่แน่ใจพฤติกรรมของ psutil บน OS ใด ให้บอกตรงๆ และแนะนำให้ทดสอบจริงบนเครื่อง อย่าเดา
- ช่วยเขียน test คู่กับโค้ดเสมอ

## 7. เรื่องที่ยังเปิดค้าง (ต้องตกลงในที่ประชุม)

- [ ] ยืนยันสูตร CPU% และ `contract.py` เวอร์ชัน 1.0
- [ ] ยืนยันตาราง mapping priority → nice / Priority Class (ดู BRIEF ของพีชและโชกุน)
- [ ] จะตั้ง CI (GitHub Actions บน `windows-latest` / `macos-latest`) หรือไม่
- [ ] ใครเป็นคนรวม PR สุดท้ายก่อนพรีเซนต์
