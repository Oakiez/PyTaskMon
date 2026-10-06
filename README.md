# PyTaskMon

เครื่องมือ Web-based สำหรับตรวจสอบและจัดการ process แบบ real-time บน **Windows** และ **macOS**
โปรเจกต์วิชา Operating Systems (Mini Project)

## ภาพรวม

PyTaskMon แสดงข้อมูล process ในรูปแบบเดียวกับ PCB (PID, PPID, state, priority, CPU, memory, threads)
พร้อมควบคุม process ได้ (kill, suspend/resume, ปรับ priority) ผ่านหน้าเว็บที่รันในเครื่องของผู้ใช้เอง
และใช้เปรียบเทียบกลไกการจัดการ process ของ Windows กับ Unix

## ฟีเจอร์

- แสดงรายการ process แบบ auto-refresh, เรียง/ค้นหา/กรองได้
- คำนวณ CPU% เอง จากการเปลี่ยนแปลงของ CPU time แล้วเทียบกับค่าจาก `psutil`
- แสดง process tree (ความสัมพันธ์พ่อ-ลูก)
- ควบคุม process: kill, suspend/resume, ปรับ priority (แสดงเป็น 5 ระดับ ไม่ขึ้นกับ OS)
- สรุปข้อมูลระบบ: CPU รวม, RAM รวม, uptime
- สาธิต zombie / orphan process (macOS เท่านั้น เพราะใช้ `os.fork()`)
- ป้องกันการ kill process สำคัญของระบบ และต้องยืนยันก่อน kill ทุกครั้ง

## ความต้องการของระบบ

- Python 3.12 หรือ 3.13 (ทั้งทีมใช้เวอร์ชันเดียวกัน)
- Windows หรือ macOS

## วิธีติดตั้งและรัน

```bash
git clone https://github.com/Oakiez/PyTaskMon.git
cd PyTaskMon

# สร้างและเปิดใช้ virtual environment
python -m venv venv

# Windows (PowerShell):
venv\Scripts\Activate.ps1
# macOS:
source venv/bin/activate

pip install -r requirements.txt

# รัน dashboard (เมื่อ app.py พร้อมแล้ว)
python app.py
```

จากนั้นเปิดเบราว์เซอร์ที่ `http://127.0.0.1:5001`

> **ความปลอดภัย:** เซิร์ฟเวอร์ bind ที่ `127.0.0.1` เท่านั้น เพราะมีปุ่มสั่ง kill process
> อย่าเปิดให้เข้าถึงจากเครื่องอื่นในเครือข่าย

> **สิทธิ์การเข้าถึง:** process ของระบบบางตัวอ่านข้อมูลหรือสั่งควบคุมไม่ได้ถ้าไม่ใช้สิทธิ์ผู้ดูแล
> field ที่อ่านไม่ได้จะแสดงเป็น "—" ไม่ทำให้โปรแกรมหยุดทำงาน

## โครงสร้างโปรเจกต์

```
PyTaskMon/
├── collector.py          # ดึงข้อมูล process (Data Layer)
├── actions.py            # เลือก implementation ตาม OS
├── actions_windows.py    # kill/suspend/priority ฝั่ง Windows
├── actions_unix.py       # kill/suspend/nice ฝั่ง Unix
├── contract.py           # data contract ที่ทุกส่วนใช้ร่วมกัน
├── app.py                # Flask entry point
├── ui/                   # templates และ static files
├── demo/                 # zombie / orphan demo (macOS)
├── tests/                # unit tests
└── docs/                 # เอกสารโปรเจกต์ และรายงาน (docs/report/)
```

> ไฟล์ที่ยังไม่มีในรายการปัจจุบันจะถูกเพิ่มเข้ามาผ่าน branch ของแต่ละคน

## สถาปัตยกรรม

แบ่งเป็น 3 ชั้น ที่สื่อสารกันผ่านรูปแบบข้อมูลใน `contract.py`

| ชั้น | หน้าที่ | ไฟล์หลัก |
|---|---|---|
| Data | ดึงและคำนวณข้อมูล process / ระบบ | `collector.py` |
| Actions | สั่งควบคุม process แยกตาม OS | `actions*.py` |
| UI | แสดงผลและรับคำสั่งจากผู้ใช้ | `app.py`, `ui/` |

หลักการสำคัญ

- **Data contract:** ทุก process อยู่ในรูปแบบเดียวกัน ดู `contract.py` (แก้ต้องแจ้งทีม)
- **Priority เป็นนามธรรม:** UI เห็นแค่ `low / below_normal / normal / above_normal / high` การแปลงเป็น nice (Unix) หรือ Priority Class (Windows) อยู่ใน `actions_*.py` เท่านั้น
- **ทุก field เป็น `None` ได้** และต้องจับ `psutil.AccessDenied`, `NoSuchProcess`, `ZombieProcess`

## ทีมงาน

| ชื่อ | หน้าที่ | Branch |
|---|---|---|
| โอ๊ค (วงศธร) | Data Layer (`collector.py`) | `feature/oak-collector` |
| พีช (คมชาญ) | Actions ฝั่ง Windows + รายงาน | `feature/peach-actions` |
| โชกุน (ภีมเดช) | UI + Actions ฝั่ง Unix + Zombie demo | `feature/shogun-ui` |

## การรันเทส

```bash
pytest
```

## แนวทางการทำงานร่วมกัน (Git)

ทีมตกลงกันเองดังนี้ (ไม่ได้ตั้ง branch protection ใน GitHub)

- ห้าม push ตรงเข้า `main` ให้ทำงานใน branch ของตัวเอง
- เปิด Pull Request เมื่องานเสร็จ และให้สมาชิกอีกอย่างน้อย 1 คน review ก่อน merge
- ห้าม force-push เข้า `main`
- Commit message ระบุส่วนงานและผู้ทำ เช่น `[collector] add process tree builder (Oak)`
- push สม่ำเสมอ อย่างน้อยสัปดาห์ละ 2-3 ครั้งต่อคน
- ตั้ง `git config user.name` / `user.email` เป็นของตัวเองก่อน commit
- ห้าม commit `.env`, token หรือ secret ใดๆ

## เอกสารเพิ่มเติม

- `docs/DECISIONS.md` — ข้อตกลงและเรื่องที่ทีมต้องตัดสินใจ
- `docs/report/` — รายงานและโครงรายงาน

## กำหนดการ

- วันพรีเซนต์: **7 ตุลาคม 2569**

## สถานะ

✅ ฟีเจอร์หลักพัฒนาครบถ้วน พร้อมสำหรับการ Demo

- [x] ตั้ง repo และโครงเริ่มต้น
- [x] ร่าง data contract (`contract.py` v0.1)
- [x] ตกลง data contract, สูตร CPU%, priority mapping
- [x] Data Layer (`collector.py`)
- [x] Actions Layer (Windows / Unix)
- [x] Web dashboard
- [x] Zombie / orphan demo (Unix)
- [ ] รายงานและสไลด์ (พีช)