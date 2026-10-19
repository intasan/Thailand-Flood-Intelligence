# Research API v0.1
Run FastAPI and open http://localhost:8000/docs (Swagger), /redoc or /openapi.json.

- GET /health/live: process liveness.
- GET /health/ready: PostGIS connectivity; 503 if unavailable.
- GET /v1/status: actual empty-data coverage status.
- POST /v1/assess: {"lat":13.75,"lon":100.5}; WGS84 point.
- POST /v1/parcels/assess: {"geometry":{"type":"Polygon","coordinates":[[[100,13],[101,13],[101,14],[100,13]]]}}; validates geometry only, no parcel-wide calculation.
- GET /v1/geocode?q=...: 503 until a licensed/self-hosted provider is implemented.

Assessment response: status unsupported; risk unknown; elevation, water level, depth, duration null. Metadata includes UTC generated_at, null observed_at and valid_at, empty provenance, null model_version, not_validated status, null resolution/datum and not_quantified uncertainty. A timestamp of response generation is never an observation timestamp. No false numerical confidence intervals.

Future approved model result serving must check coverage, valid time, validation approval, input provenance and compatible vertical datums. Database schema alone does not enable publication.

## Operator local-file import
From backend: `python -m app.ingest /absolute/observations.csv /absolute/manifest.json` with DATABASE_URL set. CSV fields: station_id, observed_at (timezone-aware ISO8601), value, unit (m). Manifest: source_id, source_url, license_evidence, vertical_datum, approved_by, approval_status=approved. Source and stations must already be independently approved in PostGIS. Import verifies matching source license and station datum; a transaction makes the batch atomic, and duplicate station/timestamp rows are immutable (`ON CONFLICT DO NOTHING`). Raw file SHA256 is stored; operator must retain raw bytes separately. Failed batch audit persistence and correction/version workflows remain to implement. Database ingestion has not been integration-tested here.

`app.terrain.sample_elevation` samples an approved local raster with CRS transform and nodata checks. It is not connected to public assessment; raster height may be DSM rather than ground DTM and must not automatically be labeled house elevation.
