# Verification record — 2026-10-19 UTC

## Executed
- Backend pytest with requirements.txt versions installed: 13 passed. Synthetic inputs exist only inside unit tests, never in dashboard/API data.
- Tests cover null/unknown public outcomes, invalid coordinates, polygon/self-intersection validation, disabled geocoder, source manifest approval, timestamp/unit/provenance gate, raw checksums, river network cycle rejection, raster CRS/bounds/NoData and liveness versus readiness.
- Next.js 16.4.2 production build including TypeScript validation: passed. MapLibre 6.15.0 uses named module imports.
- Frontend Node tests: 3 passed (coordinate validation, Google pin/viewport precedence, malformed and untrusted URL rejection).
- `npm audit --omit=dev --audit-level=high`: found 0 vulnerabilities at execution time (not a guarantee about future advisories or Docker/Python dependencies).
- Compose YAML parsed with PyYAML; this does not validate Docker runtime.

## Not executed / not validated
- Docker image builds, Compose startup and PostGIS SQL execution: Docker/Postgres binaries unavailable.
- Database importer transaction behavior and constraint integration: needs running PostGIS.
- Airflow execution: runtime not installed; DAG is an offline readiness audit, not live ingestion.
- Browser interaction, GPU map rendering, mobile viewport, geolocation permissions and external tile delivery: browser QA capability unavailable in managed environment.
- No operational datasets acquired. No hydraulic solver installed/run. No calibration, independent event validation, flood prediction or accuracy claims.
- Local checks above passed. GitHub CI results must be checked separately after upload. No hosted deployment.

Tests and frontend compilation do not establish operational hydrologic validity. Public release must wait for these integration checks and the separate pilot acceptance described in ARCHITECTURE.md.

## v0.2 execution record
- Previous v0.1 GitHub Actions run 39295313479 completed successfully.
- Local backend: 22 passed, 2 PostGIS tests skipped because local database runtime is unavailable. Those two tests are configured for real PostGIS in CI.
- Frontend: 3 coordinate tests passed; production build and TypeScript passed, including /research and the same-origin API proxy.
- Real source smoke: geocoding returned Thai Bangkok candidates; elevation endpoint returned a Copernicus DSM response for 13.75,100.5. This verifies connectivity only, not survey accuracy or a flood forecast.
- New CI jobs test PostGIS import rollback/idempotency and spatial lookup, build/start Compose with public data disabled, check database readiness/Next proxy/OpenAPI, and build Airflow and import DAGs. Final CI outcome is recorded after the run completes.
- No hydrologic pilot, independently validated operational model or hosted deployment. Browser interaction QA remains unexecuted in this environment.

- First v0.2 CI: backend/PostGIS, frontend and Airflow succeeded. Compose found Rasterio missing libexpat.so.1 in python:3.12-slim. Dockerfile now installs libexpat1/libstdc++6 and verifies GIS imports during build; full rerun pending.
- Additional local regression cases passed: null counts when database unavailable, geodesic parcel area, and unsupported model coverage. Local total: 25 passed, 2 PostGIS skips.
