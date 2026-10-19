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

## HII historical archive (v0.3)
The official catalog https://data.go.th/th/dataset/water-level and its GD Catalog mirror https://gdcatalog.go.th/dataset/gdpublish-water-level publish water-level archives under Creative Commons Attribution Non-Commercial. The catalog does not state a licence version; this software does not invent one. Attribution: สถาบันสารสนเทศทรัพยากรน้ำ (องค์การมหาชน) / Hydro-Informatics Institute. This is an archive updated monthly, not a live feed.

For non-commercial research, run the explicit import profile:
```bash
docker compose --profile hii-import run --rm hii-import
```
It downloads only canonical station metadata and CPY001 for September 2026, archives exact source bytes/checksums and imports normal-flag rows. It does not download the 803 MB archive or bulk-crawl directories. To select a different station/month, set HII_STATION and HII_MONTH in `.env`. The profile command acknowledges non-commercial use; do not run it for a commercial project without suitable permission. It is not enabled on ordinary startup. Source files remain under their original licence; repository source-code availability is not a grant of commercial data rights.

Schema migration `002_provenance.sql` adds station/observation JSON metadata. Compose now runs the idempotent migration service before API/importer startup, including existing v0.2 volumes. Back up valuable databases before upgrades. Unit/integration tests use isolated schemas.

The HII archive timestamps have no UTC offset. The importer uses explicitly selected Asia/Bangkok and stores `timestamp_status=assumed_timezone_source_has_no_offset`; it does not claim a source-verified timezone. Catalog datum is MSL as published, with no verified EGM2008 conversion. Flag N is Normal per Thaiwater Standard, not proof of independent local hydrologic validation. Missing sentinels -999/9999/999999/-/null and non-N flags are quarantined, not converted to zero. Original row line, source flag, source URL and raw file SHA256 are retained per accepted record. Conflicting corrections to immutable observations abort the batch.

Canonical 0all_stn_metadata.csv has explicit named coordinate fields. A sampled monthly metadata file had inconsistent extra columns; it is not positionally guessed or used. Station coordinates remain as published canonical metadata, not a new survey. See HII_ARCHIVE_AUDIT.json for the actually inspected station-month and readiness gaps.

Airflow DAG `hii_historical` is manual-only. Set accept_non_commercial=true when intentionally triggering a non-commercial import. It has no automatic schedule and produces no forecasts.

`/v1/observations?station_id=HII:CPY001` defaults to the last available day in the archive, not the current day. Optional start/end must be timezone-aware and span at most 31 days; results are capped at 10,000. Gaps greater than 15 minutes are reported without interpolation. This heuristic is a display aid, not the agency's official completeness rating. The dashboard labels historical readings and shows timezone/datum limitations.

## Model integrity and reviewer configuration (v0.4)
Model package schema version 2 is required. Read MODEL_REVIEW.md before installing a model. The API trust-store location is MODEL_REVIEWERS_FILE; Compose mounts `data/reviewers` separately from `data/models`, read-only. No default production reviewer public key or private key is shipped. Existing unsigned/version-1 packages intentionally become rejected; there is no bypass flag. Missing approval evidence cannot be replaced with self-asserted manifest fields.

`/readiness` and `/v1/readiness` distinguish imported archive observations, missing live feed, missing survey registry, integrity-checked reviewed packages and disabled public property risk. A database outage produces unknown counts, not zero observations or a safe-risk claim.

## v0.5 user-facing corrections
Parcel area supports valid Polygon holes regardless of ring direction. A representative point inside the parcel is used only as a display location; flood inference for the whole parcel remains unsupported. Thai area-unit display is rounded and approximate. Property GeoJSON exports include the calculated area and method label, not a flood forecast.

The browser and API now reject oversized POST bodies before geometric processing. The limit is 64,000 bytes, so very detailed polygons should be simplified with a GIS tool within the documented 1000-vertex limit. Provider cache entries are shape/type-checked before use and malformed older entries are evicted. A withdrawn source no longer contributes to public station or observation counts. WebGL initialization failure is caught so coordinate/place input can remain usable; actual browser/device testing is still outstanding.

If a local Next/Turbopack incremental cache is damaged, stop the development server, run `npm run clean` from frontend, then `npm run build`. The cross-platform clean script removes only `.next` generated output; it does not delete source, database volumes or user data. Clean rebuild was verified after an observed local cache read failure.


## v0.6: parcel files, coordinate links and station history
The dashboard accepts one WGS84 longitude/latitude Polygon, either as geometry, Feature or a one-feature FeatureCollection. All holes are retained. Files must be at most 60,000 UTF-8 bytes with at most 1,000 positions across all rings. Projected CRS declarations, 3D coordinates, unclosed rings and multiple features are rejected; topology is checked by the API before the imported overlay is displayed. No CRS conversion or cadastral certification is performed. The application does not persist submitted parcels; deployment request logging must be assessed separately.

Share links contain only a selected point, rounded to six decimal places, in the URL fragment. They contain neither parcels nor risk conclusions. Anyone receiving the link can read the location; the link opens on the same installation and submits its point for assessment.

Station history uses actual returned observations. Chart lines break at invalid values or intervals longer than 15 minutes; missing values are never filled. Display times use Asia/Bangkok (UTC+7). CSV exports preserve original offset-bearing timestamps, station datum, raw-file hash, source URL, source quality flag and timestamp-status metadata where supplied. Formula-like text is escaped for spreadsheet safety; numeric negative water levels remain numeric. Archive timestamp assumptions remain those recorded by the importer. The graph is station water level, not property flood depth.


## River-network preflight
See [RIVER_NETWORK.md](RIVER_NETWORK.md) for the offline input contract, original-source checksum verification and upstream/downstream structural audit. No network is approved, persisted or served automatically. This is a preprocessing check, not a flow or inundation model.


## Historical rainfall preparation
See [RAINFALL_INPUT.md](RAINFALL_INPUT.md) for local catchment-mean interval preparation. Requires source-linked non-overlapping catchments, explicit approved quality flags and checksums. Incomplete coverage remains null for complete-window totals. This command writes a prepared report only; no PostGIS ingestion, feed, rainfall-to-runoff conversion or model approval is performed.
