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
