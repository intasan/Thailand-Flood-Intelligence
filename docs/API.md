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

## v0.4 integrity gates and readiness
GET /v1/readiness reports actual imported-data availability and explicit unavailable/disabled capabilities. `/readiness` renders it for the public. `/v1/models/point` now requires schema-v2 evidence files and a valid enabled external reviewer signature, plus full raster value/grid checks. See MODEL_REVIEW.md for the machine contract. Missing/mismatched/revoked evidence never results in a public flood-depth value.

## v0.5 correctness and request limits
Parcel calculations normalize exterior/hole ring orientation before ellipsoidal area calculation. `location` is an interior representative point for display, not a centroid flood estimate. `perimeter_m` is the exterior boundary; `total_boundary_m` additionally includes holes. Returned area remains an approximation from user-drawn boundaries, not a cadastral survey. The Dashboard displays square metres and Thai land units (1 rai = 1600 m², 1 ngan = 400 m², 1 square wah = 4 m²), rounded consistently to 0.01 square wah.

Public station/observation counts are restricted to approved sources with licence evidence, with `count_scope=approved_licensed_sources_only`. Withdrawn sources are excluded from both map queries and public availability counts.

POST request bodies are bounded to 64,000 bytes before API JSON/GIS processing, including chunked bodies without Content-Length. The Next proxy enforces the same byte limit, a total body-read deadline and JSON media type; it forwards documented read/assessment routes only. Oversize=413, invalid media type at proxy=415, invalid UTF-8 at proxy=400, timed-out body=408. Proxy responses explicitly use Cache-Control: no-store; provider's separate server cache retains its documented TTL.

Provider payloads are validated before caching. Malformed previously cached entries are evicted and fetched again. Invalid coordinates/admin objects or elevation shapes never become cached data or fallback measurements. Empty/whitespace-only place searches are rejected before upstream access.
