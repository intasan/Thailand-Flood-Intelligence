# Historical catchment-mean rainfall preparation v1.0.0

This operator-only local-file tool prepares source-linked rainfall intervals for later modelling. No rainfall feed, rainfall-to-runoff model, public rainfall display or hydraulic solver is enabled. No real rainfall file is bundled; fixtures are synthetic tests only. Preparation is not database ingestion or source approval.

## Run
From `backend/` with requirements installed:

```bash
python -m app.rainfall_input /path/to/rainfall.csv /path/to/rainfall-manifest.json --network /path/to/network.json --network-raw-source /path/to/original-network-bundle > /path/to/prepared-rainfall.json
```

Exit 0 produces prepared JSON (possibly incomplete); exit 2 rejects input with a reason on stderr and no report on stdout. Redirection may leave an empty output file on rejection. Check both exit code and `status`; `prepared_incomplete` is not model-ready input. Nothing is downloaded, stored in PostGIS, approved or exposed publicly by this command.

The network must pass [RIVER_NETWORK.md](RIVER_NETWORK.md) v1.1.0 including complete non-overlapping incremental catchment geometries and reach coverage. Its exact package hash must match the rainfall manifest; the CLI also checks the original network source hash. If the original source consists of multiple files, preserve an original bundle with a reproducible conversion record. Neither hashes nor provenance-field presence prove scientific accuracy or legal permission.

## CSV contract
UTF-8 (optional BOM), exactly these columns in this order:

```text
reach_id,start,end,rainfall_mm,quality_flag
```

Each row describes a catchment-mean rainfall accumulation in millimetres over `[start,end)`. Both timestamps require explicit UTC offset. They are normalized to UTC in output; the raw CSV hash links back to unchanged original text. Every interval must match the configured duration and grid, stay within the window and refer to an existing reach. Input order need not be chronological. Duplicate intervals (including equivalent instants written with different offsets), off-grid intervals, unknown reaches, ambiguous timestamps, malformed rows and wrong columns reject the entire input. No implicit timezone, unit conversion or spatial interpolation is applied.

Zero is valid rainfall. Blank, negative, non-finite or nonnumeric amounts are quarantined with `rainfall_mm=null`. A flag outside the explicit accepted list also quarantines the value. No missing/sentinel value becomes zero. Absence of an entire row counts as an absent interval; no row is fabricated to fill it. Header-only files produce incomplete summaries with null totals.

## Manifest contract

| Field | Required meaning |
|---|---|
| schema_version | Integer 1 |
| source_url, license, license_evidence | Actual source and rights references |
| dataset_version, retrieved_at | Source release and offset-bearing retrieval time |
| approval_status, approved_by | `approved` and an identified operator; local assertions only |
| spatial_averaging_evidence | Reference documenting how catchment means were computed and validated |
| data_type | `historical_observation`; forecasts are rejected |
| unit | `mm` |
| quantity | `interval_accumulation`; rate units and cumulative counters unsupported |
| spatial_support | `catchment_mean`; point gauges cannot be substituted directly |
| raw_sha256 | SHA256 of exact rainfall CSV bytes |
| network_package_sha256 | SHA256 of exact network JSON bytes |
| window_start, window_end | Offset-bearing interval boundaries; end after start, at most 31 days, no future end beyond 5-minute clock allowance |
| interval_seconds | Integer 60–86,400; window duration must be divisible by it |
| accepted_quality_flags | Nonempty unique explicit list of source flags approved by the operator |

The tool does not derive catchment means from stations or rasters. Operators must supply and independently verify that spatial processing and its evidence first. Approval fields are not cryptographic signatures or authoritative registry checks. Source licence and quality-flag semantics must be reviewed before operational use.

Limits: CSV 10 MB, manifest 64,000 bytes, network JSON 20 MB, at most 100,000 expected reach×time intervals and 100,000 rows. Shorten the window or split independently meaningful study coverage if the expected grid is too large; absent intervals must not be hidden by changing study coverage.

## Results and limitations
Records preserve source line, quality flag, interval and quarantine status. Each reach summary reports expected, received, accepted, quarantined and absent interval counts. `known_interval_sum_mm` sums only accepted values and is null when none exist. It is explicitly a partial sum if coverage is incomplete. `total_rainfall_mm` is available only when every expected interval is accepted; otherwise it is null. Complete zero rainfall remains zero.

`precipitation_volume_m3 = total_rainfall_mm / 1000 × incremental_catchment_area_m2`, only for complete coverage. This describes precipitation amount over the supplied catchment, not runoff, discharge or flood volume. Infiltration, evaporation, storage, routing and tides are not modelled. Extreme arithmetic overflow rejects input rather than emitting infinity.

Output includes preparation version, generated time, manifest provenance, exact network and rainfall hashes, and `validation.status=structural_checks_only`, `hydraulic_validation=not_performed`. The CLI additionally records exact manifest hash and confirms network original-source checksum. Direct Python calls leave that latter checksum `not_checked`. No claim of measured spatial accuracy, uncertainty bounds, correct drainage divides, calibrated runoff or flood-risk prediction follows from preparation success.
