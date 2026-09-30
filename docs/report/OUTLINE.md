# โครงรายงาน PyTaskMon (ร่าง)

> เจ้าของ: พีช (ทุกคนช่วยส่งข้อมูลของส่วนตัวเอง)
> เนื้อหาเชิงทฤษฎีในไฟล์นี้เป็นจุดตั้งต้น **ต้องตรวจสอบกับตำราของวิชาและผลทดสอบจริงก่อนใส่ในรายงาน**

## 1. บทนำ
- ที่มาและวัตถุประสงค์ (ศึกษา PCB, process state, CPU utilization, signal, priority)
- ขอบเขต: ทำอะไร / ไม่ทำอะไร (ดูหัวข้อ 2 ของ handover)

## 2. ทฤษฎีที่เกี่ยวข้อง
- Process และ PCB (ข้อมูลที่ OS เก็บต่อ process เช่น PID, PPID, state, ตัวนับโปรแกรม, ข้อมูลหน่วยความจำ, ข้อมูล scheduling)
- Process state และการเปลี่ยนสถานะ
- CPU scheduling และ priority
- Signal (Unix) กับกลไกที่เทียบเคียงได้บน Windows
- Zombie และ orphan process

## 3. การออกแบบระบบ
- สถาปัตยกรรม 3 ชั้น (Data / Actions / UI) พร้อม diagram
- Data contract (อ้างอิง `contract.py`)
- Priority abstraction: ทำไม UI ไม่ควรรู้เรื่อง OS
- มาตรการความปลอดภัย: bind `127.0.0.1`, blacklist, confirm ก่อน kill, action เป็น `POST`

## 4. การพัฒนา
- **Data Layer (โอ๊ค):** การดึงข้อมูลด้วย `psutil`, สูตร CPU% ที่คำนวณเอง, process tree, การจัดการ `None` และ exception
- **Actions Layer (พีช, โชกุน):** kill / suspend / resume / priority ของแต่ละ OS
- **UI (โชกุน):** dashboard, การเรียง/ค้นหา/กรอง, กราฟ
- **Demo zombie/orphan (โชกุน):** วิธีสาธิตและผลที่เห็นใน dashboard

## 5. ผลการทดสอบ
- ผลเทียบ CPU% ที่คำนวณเอง กับค่าจาก `psutil` (ตาราง + อธิบายว่าต่างเพราะอะไร)
- ผลของ nice / Priority Class ต่อการใช้ CPU (รันโหลดสองตัวคนละ priority แล้วเทียบ)
- ผล suspend / resume: state เปลี่ยนอย่างไร
- ผล terminate vs kill
- screenshot จาก dashboard จริง และผลรัน unit test

## 6. เปรียบเทียบ Windows vs Unix (ส่วนสำคัญ)

| หัวข้อ | Windows | Unix / macOS | ที่มาของข้อมูลในรายงาน |
|---|---|---|---|
| ปรับ priority | Priority Class (หลายระดับ) และ priority ของ thread | nice value (ช่วงกว้าง ค่าน้อย = priority สูง) | ผลทดสอบ (พีช / โชกุน) |
| ยุติ process | `TerminateProcess` ทันที ไม่ให้เก็บกวาด | SIGTERM ให้ process จัดการเองได้ / SIGKILL บังคับ | ผลทดสอบ terminate vs kill |
| หยุด/เริ่มต่อ | ไม่มี signal แต่ทำได้ผ่าน API ของ OS (psutil ห่อให้) | SIGSTOP / SIGCONT | ผลทดสอบ suspend/resume |
| Process state | ชุด state ที่ `psutil` เห็นน้อยกว่า (ส่วนใหญ่ running / stopped) | มี sleeping, disk sleep, stopped, zombie ฯลฯ | ตาราง state ใน `collector.py` |
| การสร้าง process | `CreateProcess` | `fork()` + `exec()` | อธิบายเชิงทฤษฎี |
| Zombie / orphan | ไม่มีแนวคิดเดียวกัน | มี: zombie รอ parent เรียก `wait()`, orphan ถูก init/launchd รับ | demo ของโชกุน |
| สิทธิ์ที่ต้องใช้ | บาง process ต้องรันแบบ admin | บาง process ต้องใช้ root | บันทึกจำนวน `AccessDenied` ที่พบ |

> ⚠️ ช่องเนื้อหาในตารางเป็นสรุปเบื้องต้น ให้ตรวจกับผลที่ได้จากเครื่องจริงและตำราก่อนใช้

## 7. ปัญหาที่พบและข้อจำกัด
- field ที่ OS ไม่รองรับหรืออ่านไม่ได้ (ได้ `None`)
- ข้อจำกัดของ `fork()` บน Windows
- สิทธิ์การเข้าถึง process ของระบบ
- ความแตกต่างของสูตร CPU% ระหว่าง Task Manager กับ `top`

## 8. สรุปและแนวทางพัฒนาต่อ
- สิ่งที่ได้เรียนรู้ด้านการจัดการ process ของ OS
- แนวทางต่อยอด (เช่น รองรับ Linux ผ่าน `/proc`)

## ภาคผนวก
- วิธีติดตั้งและรัน (อ้างอิง README)
- รายชื่อสมาชิกและหน้าที่ + สรุป commit/PR ของแต่ละคน

## เช็คลิสต์ตัวเลขและภาพที่ต้องเก็บระหว่างทำงาน
- [ ] screenshot dashboard บน Windows และ macOS
- [ ] ตารางเทียบ CPU% (ของเราเอง vs psutil)
- [ ] screenshot zombie/orphan ใน dashboard
- [ ] ผลทดสอบ nice, SIGSTOP/SIGCONT, SIGTERM vs SIGKILL
- [ ] diagram สถาปัตยกรรม 3 ชั้น
