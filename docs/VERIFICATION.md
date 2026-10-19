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
