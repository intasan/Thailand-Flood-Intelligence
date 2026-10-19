# Local operations and data onboarding v0.2

## Bootstrap
Install Docker Engine/Desktop with Compose v2. Copy `.env.example` to `.env`, use a URL-safe random POSTGRES_PASSWORD (do not commit), and run `docker compose up --build -d`. Open http://localhost:3000 and /research. Containers bind localhost only. This is not an Internet deployment.

The database schema is applied on the first empty database volume only. Existing v0.1 databases need no schema change for v0.2. Do not run `down -v` on valuable data: it removes database volumes. Back up with `docker compose exec -T db pg_dump -U flood flood > backup.sql`.

Open-Meteo adapters are configured for non-commercial educational/research use. See https://open-meteo.com/en/terms. Disable with PUBLIC_DATA_ENABLED=false for other use until a suitable provider/account is configured. There is no automatic fallback to public Nominatim. Geocoding searches are only submitted on button click; no autocomplete. Provider cache lasts 7 days, with a shared SQLite quota of 30 upstream calls/minute and 500/day per single-host deployment. Do not horizontally replicate this cache as a way to multiply upstream quotas. Named cache volume contains provider responses; remove according to your retention policy.

## Station onboarding (operator only)
Obtain source permission, licence evidence and station datum ties first. Register real source and real stations in PostGIS using parameterized SQL through a trusted operator tool. Never insert illustrative station rows into operational databases. `sources.approval_status=approved` requires licence evidence. Station IDs must be globally namespaced by agency.

CSV columns: station_id, observed_at, value, unit. All timestamps timezone-aware; value finite, unit m, datum supplied by manifest. Archive immutable raw CSV and its SHA256 separately. Companion manifest fields: source_id, source_url, license_evidence, vertical_datum, approved_by, approval_status=approved. Import refuses unknown source/station or inconsistent licence/datum and rolls the batch back atomically. Existing station/time observations are immutable; correction revision workflows remain a limitation.

Run `python -m app.ingest /path/real.csv /path/real.manifest.json` from backend with DATABASE_URL configured. For Airflow, place real approved files in `data/inbox/*.csv` with matching `*.manifest.json`. Start `docker compose --profile pipeline up --build -d airflow`; unpause approved_observations after reviewing the folder. The DAG runs hourly and processes only local files; it does not scrape unlicensed APIs. Airflow standalone is local development only. Initial standalone credentials appear in its logs. No approved inbox means zero files imported, not zero water or flood risk.

## Reviewed hydraulic model packages
There is no solver or real pilot package in this repository. A qualified hydrologist must create, calibrate, independently validate and approve a package before ingestion/serving. Put each package in `data/models/<run-id>/manifest.json` and referenced raster assets. Model source directory is read-only in the API container. Do not put secrets, unlicensed data or test fixtures there.

The read-only Research endpoint `/v1/models/point` only serves approved packages passing manifest checks, validity period, asset hashes, raster coverage and NoData checks. Public dashboard flood risk remains unsupported until a separately reviewed risk policy and model integration are enabled. This endpoint serves maximum depth over the valid event interval, not instantaneous stage. Optional duration raster is hours; absence stays null.

Required manifest fields are documented directly in `backend/app/models.py`: model_version, solver, generated_at, valid_from/to (timezone-aware), vertical_datum, resolution_m, depth_semantics=maximum_over_valid_interval, input_manifest_sha256, input_provenance (licence evidence and hashes), uncertainty, validation, assets. Validation requires independent calibration/validation event IDs; reviewed_by/at; report_sha256; pre-agreed stage_rmse_m, extent_csi and volume_error_fraction limits and metrics; confirmations of datum, river network, boundaries, structures and convergence. Assets max_depth (m) and optional duration (h) each require a relative local path and SHA256. These are software gates, not independent scientific certification. Operator evidence must be audited; self-asserted booleans cannot establish physical validity.

## Missing prerequisites for a real pilot
Agency access and redistribution rights; surveyed DTM/cross-sections/structures; station datum transforms; upstream discharge, rainfall/runoff and downstream tide; river topology; calibration event and independent validation event; qualified reviewer and acceptance thresholds. Until these exist, depth/duration/risk must remain unsupported. The 90 m DSM is unsuitable for proving house/culvert/levee connectivity.
