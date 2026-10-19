# Thailand Flood Intelligence
ระบบเริ่มต้นสำหรับค้นหาพิกัดและตรวจสอบความพร้อมข้อมูลน้ำ แยก Public Dashboard และ Research API ไม่มีข้อมูลน้ำหรือผลพยากรณ์จำลองแสดงเป็นของจริง

## Run locally
Requires Docker Engine + Compose v2. Copy `.env.example` to `.env`, set a local `POSTGRES_PASSWORD` (URL-safe characters), then:
```bash
docker compose up --build -d
```
Dashboard http://localhost:3000 · API http://localhost:8000/docs
```bash
docker compose --profile pipeline up -d airflow
```
Airflow http://localhost:8080; development standalone only. Find generated development credentials in container logs; never expose this service publicly. The audit DAG intentionally fails until an approved manifest is supplied. There is no automatic live ingestion yet.

## Development / tests
```bash
python -m pip install -r backend/requirements.txt
cd backend
python -m pytest -q
uvicorn app.main:app --reload
```
In a second terminal:
```bash
cd frontend
npm ci
npm run dev
```
Checks: `npm test`, `npm run typecheck`, `npm run build`. Next proxies /api to localhost:8000 in development; Docker uses api:8000. Basemap uses online OSM raster tiles with attribution. Configure a licensed provider before substantial use. Do not offline-prefetch OSM tiles.

## Implemented scope
- Thai responsive Next.js/TypeScript/Tailwind dashboard, MapLibre basemap, map selection, browser GPS, coordinate/long Google Maps URL parsing.
- Click-to-draw polygon, clear/cancel, API geometry validation and metadata view.
- FastAPI schemas/OpenAPI, explicit unknown outcomes, PostGIS migration, observation provenance validator, approved local-file CSV importer, local raster sampling utility and river DAG topology validator.
- Docker definitions and offline Airflow source-readiness audit, automated backend tests and CI definition.

## Not operational yet
Place-name search, short Google link expansion, verified Thai boundary containment, public DEM sampling, live observation integration, hydraulic routing/simulation, flood depth/duration/risk outputs, parcel statistics and production operations. Map and coordinate selection cover Thailand visually; coordinates outside Thailand are accepted but always unsupported. Network/structure effects are specified, not calculated. No pilot model has been calibrated or validated.

Read docs/DATA_AUDIT.md, docs/ARCHITECTURE.md, docs/API.md and docs/VERIFICATION.md. This code is not an operational flood warning service. No deployment performed. Source uploaded to GitHub with user authorization.
