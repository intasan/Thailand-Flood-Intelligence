# Manual Airflow HII research export

DAG `hii_observation_export` wraps the tested HII observation exporter. It is unscheduled (`schedule=None`), non-catchup and limited to one active run. It does not import/download data or publish files. The HII historical station-month must already be approved and imported under its non-commercial terms. The DAG does not generate simulated values or a hydraulic validation decision.

## Start locally
With the existing .env configured, use the optional Compose pipeline profile:

```bash
docker compose --profile pipeline up --build -d airflow
```

Open the local Airflow UI at http://localhost:8080 using the local standalone credentials. Trigger `hii_observation_export` and supply all request parameters:

```json
{
  "station": "CPY001",
  "request_id": "my-research-export-001",
  "start": "2026-09-29T17:00:00Z",
  "end": "2026-09-30T17:00:00Z",
  "interval_seconds": 600,
  "accept_non_commercial": true
}
```

These are the existing historical September archive boundaries, not forecast values. Start/end and request ID default to null so accidental triggers fail. Non-commercial acknowledgement defaults to false. Params and runtime checks restrict station codes, require timezone-aware aligned windows <=31 days and 60–86,400-second intervals. Quality acceptance is fixed to HII's documented N flag.

Task `export_snapshot` calls Python functions directly; parameters are never interpolated into a shell command. Output paths cannot be supplied by a trigger: a safe request ID names one directory below `/opt/airflow/research_exports/`. IDs accept only letters/digits/underscore/hyphen, 1–64 characters. Existing directories and symlinks are rejected rather than reused. To repeat an export, choose a new request ID and retain both receipts; automatic retries are zero to avoid ambiguously reusing partially written output. Failed exports must be investigated rather than treated as completed results.

## Files and receipts
The output directory contains `observations.csv`, `observations-descriptor.json` and `provenance.json` as documented in [OBSERVATION_EXPORT.md](OBSERVATION_EXPORT.md). The existing `airflowdata` named volume persists files across container replacement; do not run `docker compose down -v` on data you intend to retain. Copy required exports out before deleting volumes. The DAG logs request/station, row counts, missing counts and CSV SHA256. XCom receives only the small receipt, not the measured records or database credentials. No external messaging or data upload occurs.

The export uses a read-only repeatable-read snapshot for source approval and observations. It does not alter database rows. An empty source, missing rights, source withdrawal, wrong datum adapter or malformed provenance fails the task. Stored timezone assumptions and licence restrictions remain unchanged; a successful task is not a newly verified timestamp, DEM/gauge datum alignment or scientific model approval.

## Runtime dependency isolation
The Airflow image intentionally does not install GDAL/Rasterio/PyProj for this observation-only task. Generic timestamp/hash/file helpers can be imported without GIS dependencies. Rainfall/network GIS imports are deferred until their actual auditing function executes; those GIS-heavy audit commands still belong in the backend environment with its full requirements. DAG-import checks alone are insufficient: CI also initializes a temporary Airflow metadata database, executes this DAG against the actual imported HII archive and verifies the resulting DagRun success and exported checksum/provenance. CI test volumes are removed afterwards.
