# Thailand Flood Intelligence — v0.6

แพลตฟอร์มวิจัยสถานการณ์น้ำ แยก Public Dashboard และ Research API ใช้ข้อมูลที่มีแหล่งอ้างอิง และไม่สร้างค่าตรวจวัด/ผลพยากรณ์ปลอม

## Quick start
ติดตั้ง Docker Desktop/Engine และ Compose v2 คัดลอก `.env.example` เป็น `.env` ตั้ง POSTGRES_PASSWORD ที่ปลอดภัยและใช้ตัวอักษรที่ไม่ต้อง URL encode แล้วรัน:
```bash
docker compose up --build -d
```
Dashboard: http://localhost:3000 · Research docs: http://localhost:3000/research · FastAPI: http://localhost:8000/docs

## มีอะไรใช้งานได้
- Next.js / TypeScript / Tailwind / MapLibre แผนที่ OSM; GPS, พิกัด, Google Maps URL แบบมีพิกัด, วาด/ย้อนจุด/ส่งออกแปลง GeoJSON
- นำเข้า Polygon GeoJSON พร้อมรูในแปลง แชร์พิกัด และดูกราฟระดับน้ำย้อนหลังพร้อมส่งออก CSV ที่เก็บ provenance
- ค้นหาชุมชน/เมืองในไทยผ่าน GeoNames / Open-Meteo พร้อมรายการให้เลือก ไม่รับประกันที่อยู่รายบ้าน
- อ่านความสูงพื้นผิว Copernicus GLO-90 ผ่าน Open-Meteo พร้อมแหล่งที่มา เวลา ความละเอียด 90 ม. และ datum EGM2008 ไม่อ้างว่าเป็นค่ารังวัดพื้นดินรายบ้าน
- ตัวนำเข้า HII archive จริงแบบมีสิทธิ์ใช้สำหรับงานวิจัยไม่ใช่เชิงพาณิชย์ พร้อมกักกันข้อมูลสูญหาย/flag ผิดปกติ ดูประวัติระดับน้ำและช่องว่างข้อมูลบน Dashboard
- Research API อ่านสถานีและค่าล่าสุดจาก PostGIS พร้อมข้อมูลเก่า/ใหม่และ datum; ไม่มีข้อมูลสถานีตัวอย่างปะปนฐานจริง
- นำเข้า CSV ที่ผู้ดูแลอนุมัติแบบ atomic/idempotent; Airflow รับไฟล์จริงจาก local inbox
- คำนวณพื้นที่แปลงที่มีรูได้ถูกทิศ แสดงไร่–งาน–ตารางวา และใช้จุดแสดงผลภายในแปลงเว้า
- ตรวจข้อมูลผู้ให้บริการก่อน cache และจำกัดขนาดคำขอก่อนประมวลผล GIS
- หน้า /readiness แสดงข้อมูลที่มีจริงและส่วนที่ยังไม่รองรับ
- ประตูตรวจรับแพ็กเกจผลแบบจำลองแบบมีลายเซ็นผู้ตรวจที่เชื่อถือและไฟล์หลักฐานจริงที่ผู้เชี่ยวชาญอนุมัติ ตรวจ checksum, validation, ช่วงเวลา, raster coverage/NoData ก่อนให้ Research API อ่าน
- Swagger/OpenAPI, Docker Compose, automated tests และ GitHub Actions พร้อม PostGIS integration และ Compose smoke tests

## ยังต้องมีเพื่อวิเคราะห์น้ำท่วมจริง
มีตัวนำเข้าระดับน้ำย้อนหลังจาก สสน. แล้ว แต่ยังไม่มี feed ระดับน้ำสด ข้อมูลสำรวจ datum และแบบจำลองพื้นที่นำร่อง ไม่มีการจำลอง 1D/2D หรือการรับรองทางอุทกวิทยาใน repository จึงยังไม่มีผลความลึก ระยะเวลาท่วม หรือความเสี่ยงจริงใน Dashboard การตรวจ metadata แพ็กเกจไม่ใช่การรับรองความถูกต้องทางฟิสิกส์ ค่าความสูงพื้นผิว 90 ม. ไม่เพียงพอใช้ลบระดับน้ำเพื่อสรุปน้ำท่วม

แผนที่ฐานเป็น OSM สำหรับการใช้งาน interactive ปริมาณต่ำเท่านั้น ต้องเปลี่ยนเป็นผู้ให้บริการที่มีสิทธิ์ก่อนขยายการใช้; ไม่มี bulk/offline tile download. Open-Meteo free endpoints ใช้สำหรับงานวิจัย/การศึกษาที่ไม่ใช่เชิงพาณิชย์เท่านั้น มี cache และโควตา ปิดได้ด้วย PUBLIC_DATA_ENABLED=false

## Development and checks
```bash
python -m pip install -r backend/requirements.txt
cd backend
python -m pytest -q
python -m uvicorn app.main:app --reload
```
อีก terminal:
```bash
cd frontend
npm ci
npm test
npm run build
npm run dev
```
PostGIS integration tests require TEST_DATABASE_URL pointing to a disposable test database. Tests create and remove isolated schemas. GitHub Actions supplies a real PostGIS service. Do not point tests at operational databases.

นำเข้าข้อมูลย้อนหลังจริง (เฉพาะการวิจัยไม่ใช่เชิงพาณิชย์): `docker compose --profile hii-import run --rm hii-import` ค่าเริ่มต้น CPY001 กันยายน 2569 ไม่ใช่ข้อมูลสด

เอกสาร: [Operations](docs/OPERATIONS.md), [API](docs/API.md), [Architecture](docs/ARCHITECTURE.md), [Data audit](docs/DATA_AUDIT.md), [Pilot readiness](docs/PILOT_READINESS.md), [Model review](docs/MODEL_REVIEW.md), [Verification](docs/VERIFICATION.md)

ยังไม่มี hosted deployment. ไม่มีข้อมูลไม่ได้หมายถึงปลอดภัยจากน้ำท่วม
