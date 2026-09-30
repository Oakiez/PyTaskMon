# BRIEF — โอ๊ค (วงศธร): Data Layer (`collector.py`)

> AI ผู้ช่วย: อ่าน `docs/AI_CONTEXT.md` และ `contract.py` ก่อน แล้วอ่านไฟล์นี้

- **Branch:** `feature/oak-collector`
- **ไฟล์ที่เป็นเจ้าของ:** `collector.py`, `tests/test_collector.py`
- **OS ทดสอบ:** Windows
- **ต้องประสานกับ:** โชกุน (UI ใช้ข้อมูลจาก `Snapshot`), พีช (ใช้ `pid`/`name`/`platform` ในการเช็ค blacklist)

## หน้าที่ของ collector

ดึงข้อมูล process และระบบทั้งหมดแล้วคืนในรูปแบบ `Snapshot` ตาม `contract.py` เท่านั้น ไม่มีการสั่งเปลี่ยนสถานะ process ใดๆ (ส่วนนั้นเป็นของ `actions_*.py`)

## งานที่ต้องทำ

### 1) ดึงรายการ process

- ใช้ `psutil.process_iter([...attrs...])` หรือเรียกเป็นรายตัวก็ได้ แต่ **ทุกการอ่านต้องอยู่ใน try/except** เพราะ process หายไปหรืออ่านไม่ได้ได้ทุกเมื่อ
- field ที่ต้องได้: `pid, name, ppid, state, cpu_percent, cpu_percent_psutil, cpu_time_s, mem_rss, mem_vms, threads, priority, nice_or_priority, platform`
- จับ `psutil.AccessDenied`, `psutil.NoSuchProcess`, `psutil.ZombieProcess` → field นั้นเป็น `None` (ห้ามข้าม process ทั้งตัว ยกเว้น `NoSuchProcess` ตอนอ่าน pid เอง)
- `platform`: `"windows"` หรือ `"macos"` (ตรวจจาก `sys.platform`)

### 2) แปลงค่าดิบให้เป็นค่านามธรรมตาม contract

- **state:** แปลงจาก `psutil.STATUS_*` เป็น `State` (`running`, `sleeping`, `disk_sleep`, `stopped`, `zombie`, `idle`, `unknown`) ค่าที่ไม่รู้จักให้เป็น `unknown` ไม่ใช่ crash
- **priority:** แปลงค่าดิบของ OS (`nice_or_priority`) กลับเป็น `Priority` ตามตาราง mapping ที่ทีมตกลง (ดู `docs/DECISIONS.md`) ค่าที่ไม่ตรงตารางเลย ให้ปัดไประดับที่ใกล้สุด หรือ `None` ถ้าอ่านไม่ได้ และเก็บค่าดิบไว้ใน `nice_or_priority` เสมอ

### 3) คำนวณ CPU% เอง

สูตรที่เสนอ (รอทีมยืนยัน): `cpu_percent = (Δcpu_time / Δwall_time) / จำนวน logical core × 100`

- เก็บการสุ่มครั้งก่อนไว้ (เช่น class `Collector` ที่มี state) `{(pid, create_time): (cpu_time, timestamp)}`
- ใช้ `(pid, create_time)` เป็นกุญแจ ไม่ใช่ `pid` อย่างเดียว เพราะ PID ถูกนำกลับมาใช้ซ้ำได้ ไม่งั้นจะคำนวณข้ามคนละ process
- `cpu_time` = `user + system` จาก `cpu_times()`
- การเรียกครั้งแรกยังไม่มีค่าก่อนหน้า → คืน `None` (หรือ 0.0 ตามที่ตกลง) ไม่ใช่ตัวเลขมั่ว
- กันหารด้วยศูนย์เมื่อ Δwall_time เล็กมาก และตัดค่าให้อยู่ในช่วง 0-100 เมื่อใช้แบบ normalize
- เก็บ `cpu_percent_psutil` จาก `Process.cpu_percent()` ของ psutil ไว้เทียบ (ข้อควรระวัง: การเรียกครั้งแรกจะได้ 0.0 เสมอ) และตัวเลขสองแบบอาจต่างกันเล็กน้อยเป็นเรื่องปกติ ให้บันทึกผลเทียบไว้ใช้ในรายงาน
- ล้าง entry ของ process ที่หายไปแล้วออกจากแคช เพื่อไม่ให้หน่วยความจำโตเรื่อยๆ

### 4) Process tree

- สร้าง `tree: dict[int, ProcessNode]` จาก `ppid → children`
- จัดการกรณี `ppid` ชี้ไปยัง process ที่ไม่มีแล้ว (orphan) และวงวน (เช่น pid 0 ที่ ppid เป็น 0 บน Windows) ห้ามวนไม่รู้จบ

### 5) สรุปข้อมูลระบบ (`SystemSummary`)

- `psutil.cpu_percent()`, `cpu_count()`, `virtual_memory()`, uptime จาก `time.time() - psutil.boot_time()`, จำนวน process

### 6) Unit test (`tests/test_collector.py`)

- ทดสอบว่า `collect()` คืนโครงสร้างตรงกับ `contract.py` (มีครบทุก key, ชนิดถูก)
- ทดสอบกับ **ข้อมูลปลอม (mock)** สำหรับกรณีที่ยากจะสร้างจริง: `AccessDenied`, `NoSuchProcess`, `ZombieProcess` → ต้องได้ `None` ไม่ crash
- ทดสอบสูตร CPU% ด้วยตัวเลขที่รู้คำตอบ (เช่น Δcpu 1 วินาที ใน Δwall 2 วินาที บน 4 core → 12.5%)
- ทดสอบ process tree (ปกติ, orphan, วงวน)
- ทดสอบว่า PID ซ้ำ (create_time ต่าง) ไม่ปนกัน

## ก่อนเริ่มเขียนโค้ด (ทำก่อน)

- [ ] ตกลงสูตร CPU% และตาราง mapping priority กับทีม (`docs/DECISIONS.md`)
- [ ] pin เวอร์ชันใน `requirements.txt` (รัน `pip freeze`)
- [ ] ตั้ง `git config user.name` / `user.email` ให้ถูกก่อน commit

## Definition of Done

- [ ] `collect()` คืน `Snapshot` ตาม contract บน Windows โดยไม่ crash แม้รันแบบไม่ใช่ admin
- [ ] ทุก field รองรับ `None`
- [ ] CPU% ที่คำนวณเองกับของ psutil ใกล้เคียงกัน และมีผลเทียบไว้ให้พีชใช้ในรายงาน
- [ ] test ผ่านทั้งหมด
- [ ] เปิด PR ให้พีชหรือโชกุน review
