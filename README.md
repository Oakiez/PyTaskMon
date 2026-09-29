# PyTaskMon

เครื่องมือ Web-based สำหรับตรวจสอบและจัดการ process แบบ real-time บน Windows และ macOS
โปรเจกต์วิชา Operating Systems (Mini Project)

## ทีมงาน

| ชื่อ | หน้าที่ | Branch |
|---|---|---|
| โอ๊ค (วงศธร) | Data Layer (`collector.py`) | `feature/oak-collector` |
| พีช (คมชาญ) | Actions ฝั่ง Windows + รายงาน | `feature/peach-actions` |
| โชกุน (ภีมเดช) | UI + Actions ฝั่ง Unix + Zombie demo | `feature/shogun-ui` |

## ฟีเจอร์

- แสดงรายการ process แบบ PCB (PID, PPID, state, priority, CPU, memory, threads)
- คำนวณ CPU% เอง เทียบกับค่าจาก `psutil`
- แสดง process tree
- ควบคุม process: kill, suspend/resume, ปรับ priority
- สรุปข้อมูลระบบ: CPU, RAM, uptime
- เปรียบเทียบกลไก Windows vs Unix (ในรายงาน)

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

จากนั้นเปิดเบราว์เซอร์ที่ `http://127.0.0.1:5000`

> **หมายเหตุด้านความปลอดภัย:** เซิร์ฟเวอร์ bind ที่ `127.0.0.1` เท่านั้น เพราะมีปุ่มสั่ง kill process
> อย่าเปิดให้เข้าถึงจากเครื่องอื่นในเครือข่าย

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
└── docs/report/          # รายงาน
```

## การรันเทส

```bash
pytest
```

## กฎการทำงานร่วมกัน (Git)

- `main` เป็น protected branch ห้าม push ตรง ต้องเปิด Pull Request และมีคน approve อย่างน้อย 1 คน
- ทำงานใน branch ของตัวเอง (ดูตารางด้านบน)
- Commit message ระบุส่วนงานและผู้ทำ เช่น `[collector] add process tree builder (Oak)`
- ห้าม force-push เข้า `main`
- ห้าม commit `.env`, token หรือ secret ใดๆ

## ข้อตกลงสำคัญ

- **Data contract:** ดู `contract.py` ห้ามแก้โดยไม่แจ้งทีม
- **Priority:** UI ใช้เฉพาะ `low / below_normal / normal / above_normal / high` ส่วนการแปลงเป็น nice / Priority Class อยู่ใน `actions_*.py`
- **Blacklist:** ห้าม kill process สำคัญของระบบ และต้อง confirm ก่อน kill ทุกครั้ง
- ทุก field ต้องรองรับค่า `None` และจับ `psutil.AccessDenied`, `NoSuchProcess`, `ZombieProcess`

## สถานะ

🚧 อยู่ระหว่างพัฒนา
