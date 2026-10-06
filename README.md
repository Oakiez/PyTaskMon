# PyTaskMon

<div align="center">

![Python](https://img.shields.io/badge/Python-3.12%20%7C%203.13-3776AB?style=flat&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0%2B-000000?style=flat&logo=flask&logoColor=white)
![pytest](https://img.shields.io/badge/pytest-passed-success?style=flat&logo=pytest&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS-blue?style=flat)

**เครื่องมือ Web-based สำหรับตรวจสอบและจัดการ Process แบบ Real-time บน Windows และ macOS**  
*โปรเจกต์รายวิชา Operating Systems (Mini Project) — นำเสนอ: 7 ตุลาคม 2569*

</div>

---

## 📌 ภาพรวมโปรเจกต์ (Overview)

**PyTaskMon** พัฒนาขึ้นเพื่อเป็นเครื่องมือศึกษาการทำงานของระบบปฏิบัติการ โดยจำลองโครงสร้างข้อมูล **PCB (Process Control Block)** มาแสดงผลในรูปแบบ Real-time Dashboard พร้อมเครื่องมือควบคุม Process และเปรียบเทียบความแตกต่างของสถาปัตยกรรมระดับแกนกลางระหว่าง **Windows (Win32 API)** และ **Unix / macOS (POSIX)**

---

## ✨ ฟีเจอร์หลัก (Key Features)

- **📊 Real-time PCB Monitor:** แสดงข้อมูลสำคัญของ Process ครบถ้วน (PID, PPID, Process State, Abstract Priority, CPU%, Memory RSS/VMS, Threads)
- **⚡ Dual CPU Calculation:** คำนวณค่า CPU% อิสระจากผลต่างเวลา `((Δcpu_time / Δwall_time) / cores) × 100%` ควบคู่กับการเทียบเคียงค่าจาก `psutil`
- **🌲 Process Tree Visualization:** แสดงความสัมพันธ์ลำดับชั้น Process พ่อ-ลูก (Parent-Child Hierarchy)
- **🕹️ Cross-Platform Process Control:**
  - **Kill Process:** ปิด Process พร้อม Modal ยืนยันความปลอดภัย
  - **Suspend / Resume:** สั่งหยุดพักชั่วคราวและสั่งทำงานต่อ
  - **Priority Adjustment:** ปรับ Priority เสมือน 5 ระดับ (`low`, `below_normal`, `normal`, `above_normal`, `high`) แปลงตาม OS อัตโนมัติ
- **🛡️ Safety Blacklist Protection:** ระบบป้องกันการสั่ง Kill Process สำคัญของระบบปฏิบัติการ (เช่น `System`, `csrss.exe`, `services.exe` บน Windows หรือ `launchd`, `kernel_task` บน macOS)
- **🎨 Modern Dark Dashboard:** UI สไตล์ GitHub Dark Theme, กราฟ Resource รวมแบบ Real-time, ระบบ Search/Filter ทันใจ และ Favicon Mascot ประจำระบบ
- **🧟 Zombie / Orphan Demo:** สคริปต์สาธิตการเกิดและจัดการ Zombie/Orphan Process บนระบบ POSIX/macOS

---

## 🔬 การเปรียบเทียบเชิงลึก: Windows vs POSIX (OS Concepts)

| หัวข้อ (OS Concept) | Windows (Win32) | Unix / macOS (POSIX) |
|---|---|---|
| **Process State Control** | Win32 API (`SuspendThread` / `ResumeThread` หรือ Native NT API) | POSIX Signals (`SIGSTOP`, `SIGCONT`) |
| **Process Termination** | `TerminateProcess(hProcess, exitCode)` | Signals (`SIGTERM` ร้องขอ / `SIGKILL` บังคับปิด) |
| **Priority Mechanism** | Priority Classes (`IDLE`, `BELOW_NORMAL`, `NORMAL`, `ABOVE_NORMAL`, `HIGH_PRIORITY_CLASS`) | Nice Values (ช่วงค่า `-20` ถึง `19`) |
| **Zombie / Orphan** | ไม่มี Zombie Process จริง (Handle Table จัดการ lifecycle) | มีสถานะ Zombie (`Z`) จนกว่า Parent จะ `wait()` / Orphan จะถูก Reparent ไปยัง Init/Launchd (`PID 1`) |

---

## 📂 โครงสร้างโปรเจกต์ (Project Structure)

```
PyTaskMon/
├── app.py                # Flask Server entry point & API route handlers
├── collector.py          # Data Layer: เก็บและคำนวณสถิติระบบและ Process
├── contract.py           # Data Contract กลาง (Type hints, Data structures, Enums)
├── actions.py            # Facade เลือกระบบปฏิบัติการอัตโนมัติ (OS Dispatcher)
├── actions_windows.py    # Process actions ผ่าน Windows Win32 / psutil
├── actions_unix.py       # Process actions ผ่าน POSIX signals (macOS / Linux)
├── demo/                 # สคริปต์สาธิต zombie_orphan.py สำหรับ macOS
├── tests/                # Automated Unit Tests (pytest)
├── ui/                   # Frontend Web Assets
│   ├── templates/        # Jinja2 HTML Templates (index.html)
│   └── static/           # CSS, JavaScript (Real-time polling & Charts) และ Favicon
└── docs/                 # เอกสารข้อตกลงและบริบททางเทคนิค (DECISIONS.md, AI_CONTEXT.md)
```

---

## 🚀 วิธีติดตั้งและรันระบบ (Getting Started)

### 1. ความต้องการของระบบ (Prerequisites)
- **Python:** 3.12 หรือ 3.13
- **OS:** Windows 10/11 หรือ macOS

### 2. ติดตั้งโปรเจกต์
```bash
git clone https://github.com/Oakiez/PyTaskMon.git
cd PyTaskMon

# สร้างและเปิดใช้งาน Virtual Environment
# บน Windows (PowerShell):
python -m venv venv
venv\Scripts\Activate.ps1

# บน macOS / Linux:
python3 -m venv venv
source venv/bin/activate

# ติดตั้ง Dependencies
pip install -r requirements.txt
```

### 3. รันเว็บเซิร์ฟเวอร์
```bash
python app.py
```
เปิดเบราว์เซอร์แล้วเข้าสู่: **`http://127.0.0.1:5001`**

> **🔒 หมายเหตุความปลอดภัย:** เซิร์ฟเวอร์ Bind เฉพาะ `127.0.0.1` (Localhost) เท่านั้น เพื่อความปลอดภัยจากการสั่งการระบบ

---

## 🎬 ขั้นตอนการสาธิต (Demo Guide)

1. **ภาพรวมระบบ:** เปิดหน้า Dashboard ตรวจสอบกราฟ CPU/RAM รวม, Uptime และตาราง Process
2. **การค้นหาและเรียงลำดับ:** ทดสอบพิมพ์ชื่อ Process หรือ PID ในช่อง Search และคลิกหัวตารางเพื่อจัดเรียง
3. **การทดสอบโหลดด้วย Process จำลอง:**
   - เปิด Terminal ใหม่แล้วรันคำสั่ง:
     ```powershell
     python -c "while True: pass"
     ```
   - สังเกต Process `python.exe` กิน CPU พุ่งขึ้นมาบน Dashboard
4. **การควบคุม Process จำลอง:**
   - **เปลี่ยน Priority:** สั่งปรับเป็น `high` หรือ `low`
   - **สั่ง Suspend:** CPU ตกเป็น 0% (สถานะเปลี่ยนเป็น stopped)
   - **สั่ง Resume:** CPU กลับมาทำงานต่อ
   - **สั่ง Kill:** มี Popup Modal ให้ยืนยันก่อนปิด Process จริง
5. **ทดสอบระบบความปลอดภัย (Safety Blacklist):**
   - ทดลองกดปุ่ม Kill กับ Process ของระบบ เช่น `System` หรือ `csrss.exe`
   - ระบบจะปฏิเสธคำสั่งทันที พร้อมแจ้งเตือนว่า Process อยู่ใน Blacklist ป้องกันระบบเสียหาย

---

## 🧪 การทดสอบ (Testing)

โปรเจกต์มีชุด Automated Unit Tests ครอบคลุมการทำงานของ Data Collector, Actions และ Contracts:

```bash
pytest
```
*(ผลการทดสอบ: ผ่านครบ 39 passed, 13 skipped สำหรับ OS-specific tests)*

---

## 👥 สมาชิกและหน้าที่รับผิดชอบ (Team Members)

| สมาชิก | บทบาทหน้าที่ | Branch หลัก |
|---|---|---|
| **โอ๊ค (วงศธร)** | Data Layer (`collector.py`), Thread-safe Collector, Data Contract, Integration Lead | `feature/oak-collector` |
| **พีช (คมชาญ)** | Windows Actions (`actions_windows.py`), Win32 Integration, สไลด์นำเสนอ | `feature/peach-actions` |
| **โชกุน (ภีมเดช)** | UI/UX Dashboard (`ui/`), POSIX Actions (`actions_unix.py`), Zombie/Orphan Demo | `feature/shogun-ui` |

---

## 📅 สถานะโปรเจกต์ (Project Status)

- [x] ตกลงและกำหนด Data Contract กลาง (`contract.py`)
- [x] พัฒนา Data Collector และคำนวณ CPU% ด้วยการเทียบ Delta เวลา
- [x] พัฒนา Actions ควบคุม Process แยกแพลตฟอร์ม (Windows / macOS)
- [x] ป้องกันความปลอดภัยด้วย Blacklist และ Modal Confirmation
- [x] พัฒนา Web Dashboard แบบ Real-time พร้อม Dark Theme และ Responsive Charts
- [x] พัฒนาสคริปต์สาธิต Zombie / Orphan Process สำหรับ Unix
- [x] ทดสอบ Unit Tests ครบถ้วนทุกโมดูล
- [x] เตรียมข้อมูลสำหรับสไลด์การนำเสนอ (7 ต.ค. 2569)