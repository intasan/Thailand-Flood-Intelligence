# Verification record — v0.2 — 2026-10-19 UTC

## Verified source and CI
Code commit: `3ff7bde6d4fc0173988e8e7484ee06740e4cf018`.
GitHub Actions run: https://github.com/intasan/Thailand-Flood-Intelligence/actions/runs/39296900798
All four jobs completed successfully:

| Job | Actual checks |
|---|---|
| backend | 27 tests passed on a real PostGIS service. Includes approved import idempotency, atomic rollback on unknown stations, spatial lookup, stale observations, invalid geometry/coordinates, explicit unknown outcomes, provider failures/caching/quotas, raster NoData and reviewed-model time/asset/metric gates. |
| frontend | Node coordinate tests and Next production build including TypeScript; /research and same-origin API proxy compiled. |
| compose | Built API/web images, initialized PostGIS schema, started db/api/web containers and successfully called /health/ready, /api/v1/status and /api/openapi.json through the Next proxy. Public upstream data disabled for deterministic smoke tests. |
| pipeline | Built the custom Airflow image and imported DAGs without errors, including approved_observations. |

The initial Compose test caught Rasterio's missing libexpat.so.1 in python:3.12-slim. Dockerfile now installs libexpat1/libstdc++6 and checks GIS imports during build. The successful run above includes this correction.

## Real source connectivity
Live calls returned Bangkok location candidates and a Thai-language result for กำแพงแสน. The elevation adapter retrieved a Copernicus GLO-90 surface response for 13.75,100.5. FastAPI endpoints returned HTTP 200 through TestClient against those real/cached source adapters. Source release, fetch time, cache status, datum, attribution and limitations remain distinct. These are connectivity checks, not survey-accuracy or flood-forecast validation.

## Important verification limits
- No browser interaction, WebGL map rendering, GPS permission flow or mobile visual QA was executed in this environment. Compilation and HTTP smoke tests do not prove those UI behaviors.
- Airflow image and DAG import passed, but a full scheduled execution with operational station files has not occurred: no approved real station input was supplied. Local-file ingestion itself passed real PostGIS integration tests.
- Model fixtures are synthetic unit-test-only files, never seeded into app data or served as operational results. No real hydraulic solver, calibrated pilot, independent flood-event validation or scientifically certified package exists here.
- Model-package metadata checks enforce software preconditions; operator assertions and checksums alone cannot certify physical validity.
- No real water-level source is connected, no depth/duration/risk forecast is shown on the Public Dashboard, and no hosted deployment was performed.
- Public APIs and map tiles have usage/licence limits. A successful response is not unlimited production entitlement; see DATA_AUDIT.md and OPERATIONS.md.

Local backend execution: 25 passed and 2 PostGIS tests skipped because no local database runtime exists. The remote backend CI supplied real PostGIS and passed all 27, with no skips. CI warnings are dependency deprecations, not test failures.

## v0.3 — HII historical source, schema and UI
Tested code commit: `5790877c4d06945110d198bc866b6ba8c97737e9`.
Verified GitHub Actions run: https://github.com/intasan/Thailand-Flood-Intelligence/actions/runs/39298275779
All four jobs completed successfully:
- Backend: 31 tests passed, including real PostGIS schema migration, HII provenance import idempotency, archive-series gaps and previous regression cases. Local-only run had 28 passes and 3 database skips; remote CI supplied PostGIS and had no skips.
- Frontend: coordinate tests, TypeScript and production build passed for station history/metadata UI.
- Pipeline: custom Airflow image built; manual `hii_historical` and other DAGs imported without errors. This does not claim a full Airflow task execution.
- Compose: db → additive migration → API/web startup passed. Real HII canonical metadata and CPY001 September 2026 CSV were downloaded within the importer container, 4,304 rows inserted, 16 quarantined; the same raw-file SHA256 matched local inspection. The Next proxy successfully returned 145 observations covering the final available 24-hour interval (inclusive endpoints). No operational dataset was fabricated.

HII history is monthly published archive data, not a live feed. Source timestamps lack an offset and retain an explicit Asia/Bangkok assumption. The MSL-to-EGM2008 transformation is unverified. Only N-flag data pass this import policy; this does not certify physical accuracy. Raw source files are not bundled into the source repository. The data licence remains non-commercial attribution as stated by the official catalog.

No browser/WebGL/GPS visual-interaction test, live gauge feed, independently calibrated hydraulic pilot, property flood-risk calculation or hosted deployment has been completed. See PILOT_READINESS.md for concrete missing inputs. The passing software tests do not remove those scientific and data limitations.

## v0.4 — signed evidence, raster integrity and readiness
Tested code commit: `54b44e9a097706c725ed82488490f45f0af9265d`.
Verified GitHub Actions run: https://github.com/intasan/Thailand-Flood-Intelligence/actions/runs/39300008517
All four jobs completed successfully:
- Backend: 43 passed against real PostGIS. Includes trusted-signature success, tampered manifest/evidence rejection, missing evidence, unknown/revoked signer, unsigned v1 rejection, duplicate JSON keys, invalid cells outside the sampled location, raster datum mismatch and mismatched depth/duration grids. Test signing keys are generated ephemerally; none are production trust anchors.
- Frontend: coordinate tests, TypeScript and production build passed, including /readiness.
- Compose: API/web/database startup and readiness/OpenAPI HTTP checks passed. Real HII import still inserted 4,304 accepted rows, quarantined 16, and returned 145 final-day archive observations through the Next proxy.
- Pipeline: Airflow image and DAG imports passed.

Local backend result was 40 passed / 3 database skips; remote CI ran all 43 without skips. Warning messages are dependency deprecations. Browser interaction/WebGL/GPS testing remains unexecuted.

Schema-v2 review evidence and an external enabled Ed25519 reviewer key are now mandatory for research model outputs. No production reviewer or hydraulic package is configured. Integrity checks do not certify the reviewer or model physics; human verification remains required. No live-water adapter, surveyed pilot registry, public property-risk output or hosted deployment has been enabled.

A direct HTTP check of the official October 2026 archive directory returned 200 with no CSV links at inspection. This records the observed archive state only and does not establish whether other agencies have live data. The platform continues to label historical data explicitly and reports the live feed as not_configured.

## v0.5 — parcel correctness, cache recovery, bounded requests and public counts
Tested code commit: `53994131fb4f102e295ec992992cab8e925db4f7`.
Verified CI: https://github.com/intasan/Thailand-Flood-Intelligence/actions/runs/39301445818
All four jobs completed successfully:
- Backend: 53 passed with real PostGIS, including concave-parcel display-point containment; area invariance for reversed hole direction; hole/exterior boundary distinction; multi-byte and chunked body limits; unchanged valid-body replay; whitespace search rejection; malformed provider response rejection and old-cache recovery; withdrawal of a source from public counts and spatial queries.
- Frontend: 10 Node tests passed for API route restrictions, streaming UTF-8 byte limits, media type, malformed encoding, total body-read timeout, Thai area conversion/rounding and existing coordinate parsing. Production build and TypeScript passed.
- Compose: full db/migration/API/web stack passed health, proxy/OpenAPI/readiness checks and a JSON POST assessment through the Next proxy. Real HII archive import/query still passed.
- Pipeline: Airflow image and DAG import checks passed.

Local backend: 49 passes, 4 database skips; CI ran all 53 with no skips. A local Turbopack incremental-cache read failure was corrected by removing generated .next output with the new cross-platform clean script; clean production build then passed. No source or user data were removed.

Parcel areas remain approximate ellipsoidal calculations from submitted boundaries, not certified land surveys. Display points are for location display only; no parcel flood inference is derived. Invalid provider payloads are never cached as usable data. Body limits apply before JSON/GIS processing. Public counts exclude withdrawn/unlicensed sources.

WebGL initialization failure is handled in code to preserve location inputs, but browser interaction/WebGL/GPS visual testing remains unexecuted. There is still no live gauge feed, calibrated operational hydraulic pilot, property-risk forecast or hosted deployment. Software checks above do not establish hydrologic validity.

## v0.6 — parcel import, coordinate sharing and archive charts
Tested code commit: `b3a3ab308296b6f3f56695035f3168a421685a11`.
Verified CI: https://github.com/intasan/Thailand-Flood-Intelligence/actions/runs/39302851851
All four jobs completed successfully:
- Backend: all 53 tests passed with real PostGIS. Local run: 49 passed, 4 database-dependent skips.
- Frontend: 20 tests passed; TypeScript and production build passed. New coverage includes preservation of all polygon hole rings, rejection of projected/3D/multi-feature/unclosed/oversized files, coordinate share-link parsing, missing/invalid-observation line breaks, zero/negative water levels, chronological-domain validation and CSV provenance/formula escaping.
- Compose: database/migration/API/web health, proxy and assessment checks passed; actual CPY001 September 2026 archive import accepted 4,304 rows and quarantined 16 of 4,320; subsequent observation queries passed.
- Pipeline: Airflow image build and DAG imports passed.

Imported GeoJSON is not considered valid until the API accepts its topology. Coordinate links disclose the selected point to recipients; no parcel boundary or risk result is embedded. Station charts show actual returned history in Thai time, never filled values or inferred property flood depth. CSV preserves supplied source and timestamp-assumption metadata.

Browser interaction, WebGL/GPS and visual QA remain unexecuted. No deployment was performed. There is still no live gauge feed, surveyed/calibrated operational hydraulic pilot or property flood-risk forecast. Passing software checks does not establish hydrologic validity.

## River-network preflight — audit v1.0.0
Tested code commit: `2e8f0c49f01696f63645084091c27ec35e4f16d8`.
Verified CI: https://github.com/intasan/Thailand-Flood-Intelligence/actions/runs/39303583056
All four jobs passed:
- Backend: 72 passed with real PostGIS (local: 68 passed, 4 database skips). The 19 new synthetic-fixture cases cover confluence area accumulation, unknown/zero areas, missing or duplicate links, reversed geometry, cycles, invalid coordinates/numbers/provenance, explicit outlets, long 1,100-reach traversal, endpoint tolerance, CLI raw-source/package hashes and rejection without stdout on corrupt/mismatched input.
- Frontend: existing 20 tests and production build passed; no frontend source changes in this increment.
- Compose: full db/API/web smoke checks and actual HII archive import/query passed.
- Pipeline: Airflow image and DAG import checks passed.

The CLI is an offline preprocessing tool only; it performs structural validation and incremental-area accumulation, not discharge routing or inundation. No real Thai network has been registered or independently verified. Provenance-field presence and a matching source checksum do not authenticate source rights or flow direction. Catchment overlap cannot be checked without polygons. One-downstream acyclic representation excludes bifurcations and reversing/tidal flow. The audit does not approve any hydraulic model, infer property accessibility or enable public risk results. No deployment was performed. Browser/WebGL/GPS QA and an operational independently validated hydraulic pilot remain outstanding.

## Incremental catchment geometry — network audit v1.1.0
Tested code commit: `29472ac83103ca8a291d2da166b5e7c7803c4384`.
Verified CI: https://github.com/intasan/Thailand-Flood-Intelligence/actions/runs/39304797846
All four jobs passed:
- Backend: 91 tests passed with real PostGIS (local: 87 passed, 4 database skips). Nineteen new synthetic-fixture cases cover shared boundaries, actual overlap across outlets, identical polygons, holes/orientation/MultiPolygon, islands in holes, invalid/partial geometry/provenance, unclosed/3D/antimeridian shapes, reach coverage, scalar/geometry area agreement, geometry-based downstream accumulation, bounded spatial candidates and CLI source integrity.
- Frontend: 20 existing tests and production build passed; frontend source unchanged in this increment.
- Compose: db/API/web smoke tests and real HII archive import/query passed; 4,304 rows accepted, 16 quarantined.
- Pipeline: Airflow image and DAG import checks passed.

Catchment tests use synthetic fixtures only; no real Thai catchment or network has been accepted. When complete optional geometries are supplied, overlap and reach coverage are checked and WGS84 ellipsoidal areas are accumulated. Scalar-only operation remains explicitly unverified. Non-overlap does not establish correct drainage divides, gap-free basin coverage or property accessibility. No discharge routing, calibrated hydraulic model, flood-risk forecast or deployment was added. Browser/WebGL/GPS QA remains unexecuted.

## Historical catchment-mean rainfall preparation v1.0.0
Tested code commit: `f82b00ea04490561ceb1f2d4d1752c334caedca8`.
Verified CI: https://github.com/intasan/Thailand-Flood-Intelligence/actions/runs/39306034971
All four jobs passed:
- Backend: 129 passed with real PostGIS. Local full suite before the final two test additions: 123 passed / 4 database skips; the final targeted rainfall suite passed all 38 cases. New synthetic-fixture cases cover known-zero versus absent/quarantined rain, partial versus complete totals, interval/timezone/grid validation, equivalent-offset duplicates, metadata/rights/hash/unit/support rejection, future/forecast rejection, catchment coverage, arithmetic overflow, multiple intervals and CLI original-source/manifest integrity.
- Frontend: existing 20 tests and production build passed; no frontend source change.
- Compose: complete db/API/web smoke checks and actual HII historical import/query passed.
- Pipeline: Airflow image and DAG import checks passed.

The new CLI prepares local source-linked JSON only; it does not ingest a live rainfall feed or change PostGIS. All rainfall fixtures are synthetic and remain tests. No real catchment rainfall package is configured. Catchment-mean spatial processing and operator assertions require independent review. Complete precipitation volume is not runoff or discharge; missing intervals never become zero. No rainfall-to-runoff conversion, hydraulic routing, tide/barrier model, calibrated pilot, public flood-risk output or deployment was added. Browser/WebGL/GPS testing remains outstanding.

## Local DEM integrity audit v1.0.0
Tested code commit: `a1ccf405b27f9f6d1c6954e5149ba4e6749f7677`.
Verified CI: https://github.com/intasan/Thailand-Flood-Intelligence/actions/runs/39308404346
All four jobs passed:
- Backend: 156 tests passed with real PostGIS (local: 152 passed, 4 database skips). Twenty-seven new synthetic raster cases cover zero/negative elevations, masked versus unmasked non-finite pixels, entirely missing terrain, degree-versus-metre resolution, invalid metadata/checksums/CRS, rotated/south-up grids, bands/scales/units/datum contradictions, external masks, bounded edge-window scanning, JSON-safe NaN NoData, pixel limits and CLI success/rejection.
- Frontend: existing 20 tests and production build passed; no frontend source change.
- Compose: db/API/web smoke checks and actual HII historical import/query passed.
- Pipeline: Airflow image and DAG import checks passed.

The DEM CLI scans one local self-contained GeoTIFF and emits a read-only report. No real DEM was imported, no pilot boundary coverage was established and no vertical datum transformation or surveyed accuracy check was performed. Integrity success can coexist with no usable pixels; coverage status explicitly distinguishes this. Native geographic pixel spacing is never reported as metres. No calibrated hydraulic pilot, property-risk forecast or deployment was added; browser/WebGL/GPS QA remains outstanding.
