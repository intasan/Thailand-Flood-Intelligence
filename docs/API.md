# Research API v0.2
Swagger http://localhost:8000/docs · same-origin docs http://localhost:3000/research · schema /api/openapi.json

| Endpoint | Contract |
|---|---|
| GET /health/live | Process liveness only |
| GET /health/ready | Checks PostGIS connectivity, 503 if missing |
| GET /v1/status | Actual database counts or explicit unavailable/null, approved model package count and validity periods |
| GET /v1/geocode?q=Bangkok | Thai settlements/postcodes from GeoNames via Open-Meteo; user chooses candidate; empty matches stay empty; failures 503 |
| GET /v1/elevation?lat=13.75&lon=100.5 | Approx. 90 m Copernicus DSM; source, release, fetch time, EGM2008, limits; no local survey or house-ground claim |
| GET /v1/stations?lat=13&lon=100&radius_km=20 | Approved nearby stations (max 30), latest observations, source, datum, checksum, age. Station reading is not property water level |
| POST /v1/assess | JSON lat/lon; unknown flood risk until operational model integration |
| POST /v1/parcels/assess | Valid WGS84 Polygon, max 1000 vertices including holes. Geodesic area/perimeter and geometry; no centroid-only parcel flood inference |
| GET /v1/models/point?lat=13&lon=100&at=2026-01-01T00:00:00Z | Read-only reviewed raster package serving. Defaults to current UTC. Explicit maximum-over-event depth semantics; unsupported coverage/time/NoData stays null. No automatic asset-risk category |

Assessment metadata: UTC generated_at is response time, not an observation timestamp. Missing observations, model versions, uncertainty or datums remain null/not_validated. No numeric confidence interval without evidence.

Public provider adapters use cache and single-host shared quotas, never arbitrary fetch URLs. They can be disabled with PUBLIC_DATA_ENABLED=false. Source timestamps and dataset release are distinguished. Seven-day cached fetch time is displayed; no claim of a new terrain survey.

Operator import and hydraulic package contracts: see OPERATIONS.md. API exposes no unauthenticated write/approval endpoint. Raw-file ingestion performs a transaction and keeps existing station/timestamp records immutable; correction revisions require separate work.

## v0.3 additions
`GET /v1/observations?station_id=HII:CPY001&start=<aware-ISO>&end=<aware-ISO>` returns approved-station metadata, raw-checksum-linked observations, timestamps, source flags, explicit timezone assumptions and gaps without interpolation. Default interval is the final available 24 hours in the archive, not current conditions. Limit: 31 days / 10,000 rows. Unknown station 404, bad interval 422, unavailable database 503.

Nearby stations now include `station_metadata` and `observation_metadata`. Historical source identity, timezone assumptions and source provenance must remain visible when consumers display these data.
