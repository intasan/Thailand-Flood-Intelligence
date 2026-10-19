# HII historical observation export v1.0.0

Read approved historical HII water-level observations from PostGIS into an exact-time comparison input, preserving original source checksums, quality flags and timestamp assumptions. This exports actual imported observations only. It does not invent or generate simulated levels, transform datums, calibrate a model or publish risk results.

## Run
Inside a configured backend environment with DATABASE_URL:

```bash
python -m app.observation_export --station HII:CPY001 --start 2026-09-29T17:00:00Z --end 2026-09-30T17:00:00Z --interval-seconds 600 --accepted-flag N --destination /path/to/new-export
```

The date range is a historical example supported by the existing September 2026 importer. It requests 30 September in Asia/Bangkok, expressed in UTC. The station-month must already have been imported under its approved non-commercial-use conditions; see DATA_AUDIT.md and OPERATIONS.md. No archive download is performed here.

For Docker Compose, use `docker compose exec -T api python -m app.observation_export ... --destination /tmp/new-export` with the same arguments. Output is inside that container; copy it out before removing the container. The CLI requires a new destination directory whose parent already exists. It never overwrites an existing export directory. Exit 0 reports exported/accepted/absent row counts and filenames; exit 2 rejects the export. SQL uses a repeatable-read read-only transaction so source approval, station metadata and rows come from one database snapshot. It changes no source approval or database rows. Approval can change after the snapshot: recheck rights/status before later use.

## Files

| File | Contents |
|---|---|
| observations.csv | station_id,observed_at,value_m,quality_flag; compatible with the observation side of LEVEL_VALIDATION.md |
| observations-descriptor.json | CSV hash, published datum, stored source/licence evidence, explicit accepted N flag and source-file identity |
| provenance.json | Station metadata, explicit study window/grid, row/gap counts and each exported row's original raw-file hash, source line/URL, quality flag and time assumptions |

The output is a machine comparison dataset, not a spreadsheet-formatted CSV. Preserve station IDs and values unchanged when consuming it. `dataset_version` describes the exact source-file hashes (`raw-files-sha256:...`), not an invented agency release number. `retrieved_at` is explicitly the database snapshot export time; it is not claimed to be the original source-download time. The original published dataset release may remain unavailable.

Only the registered `HII_WATER_LEVEL_ARCHIVE` adapter with its exact published HII MSL datum descriptor is supported. This prevents an arbitrary station's relative gauge stage from being relabelled as water-surface elevation. Only the documented N flag can be accepted in this version. Other flags retain their identity and export blank numeric values. Timestamp, unit, original checksum, historical data type and required source/time provenance must be present. Original timestamps lacking offsets retain `timestamp_status=assumed_timezone_source_has_no_offset` and source timezone, rather than becoming confirmed timestamps through export.

Start/end must carry offsets. Window is `[start,end)`, positive and at most 31 days; duration must align to the explicit 60–86,400-second interval. Every actual row must lie on that grid and be unique; off-grid data reject the export rather than being rounded or resampled. At most 10,000 database rows may be exported. Empty input rejects. Source withdrawal or missing rights evidence rejects before files are created. Missing intervals are counted, not filled; zero and negative elevations stay valid. The HII importer already quarantines documented sentinel values and source quality issues; this exporter does not reconstruct quarantined source records.

## Use for model comparison
Copy the descriptor into the `observations` field of a separately reviewed comparison manifest. Choose held-out event/station/window definitions and supply the actual solver's `simulations` CSV/descriptor and independently checked datum-alignment evidence. Do not create a simulated CSV by copying observations or label it as independent validation. This command creates neither that simulated CSV nor a complete comparison manifest, because the model run and alignment evidence do not yet exist in this project.

The HII source is historical, not a live flood feed. Its published MSL convention is not reconciled with EGM2008 or a pilot DEM. Export does not resolve original timezone uncertainty, authenticate source rights, prove calibration-event independence or certify hydraulic accuracy. Non-commercial licence restrictions remain unchanged. Keep the original source archive and import audit available to verify row-level provenance; these JSON files are not signed approval evidence.

## Verification
Compose CI imports the actual CPY001 September 2026 archive, exports the final local calendar day, checks the exported CSV hash, source licence and original timezone assumptions, then reads the CSV using the model-comparison loader. No simulated series is generated in that check. Isolated PostGIS tests additionally check unchanged observation counts and rejection after source withdrawal; unit fixtures remain synthetic.
