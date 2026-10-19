# Exact-time station level comparison v1.0.0

Read-only preparation of reproducible station water-surface-elevation error metrics from two local CSV files. It does not run a solver, certify a model, issue acceptance thresholds or enable public flood outputs. No real model series or validation gauges are bundled; all new fixtures are synthetic tests only.

## Run
From `backend/` with requirements installed:

```bash
python -m app.level_validation /path/to/observations.csv /path/to/simulations.csv /path/to/comparison-manifest.json > /path/to/comparison.json
```

Exit 0 emits a comparison report, possibly incomplete; exit 2 rejects malformed/unsupported input with stderr and no success report on stdout. Shell redirection can leave an empty output on failure. A complete comparison is not a passing scientific validation. No registry/database updates, evidence signatures, external writes or model approval occur.

## Inputs
Both UTF-8 CSVs (optional BOM) require exactly these columns:

```text
station_id,observed_at,value_m,quality_flag
```

These column names apply separately to observed and simulated series. Simulation values are never labelled measured observations. Timestamps require offsets and are converted to UTC for matching. Rows may arrive unordered. Station/time keys must be unique, including equivalent timestamps written with different offsets. Each time must lie on the declared grid in `[window_start,window_end)`. Unknown stations, off-grid/out-of-window times, duplicate keys and malformed rows reject input. There is no nearest-time matching, lag optimization, interpolation, resampling or automatic correction of gauge zeros.

Zero and negative datum elevations are valid. Blank/nonnumeric/non-finite values and flags outside the explicitly accepted source-specific list are quarantined. Missing rows and quarantined rows are counted separately for both series; neither becomes zero. Finite sentinels cannot be inferred generically: normalize documented source sentinel codes to blank and retain that conversion evidence before using this tool. In particular, a numeric sentinel such as -999 must not be silently treated as a measured elevation merely because it is finite.

## Manifest

| Field | Contract |
|---|---|
| schema_version | Integer 1 |
| event_id | Named held-out study event |
| calibration_event_ids | Explicit unique list of declared training/calibration event IDs; must not contain event_id |
| datum_alignment_evidence | Reference proving consistent surveyed gauge/model datum and any applied transformation |
| station_ids | Explicit nonempty unique list of all expected stations |
| window_start, window_end | Offset-bearing boundaries; positive interval at most 31 days |
| interval_seconds | Integer 60–86,400; study duration divisible by it |
| observations | Descriptor for actual measured series |
| simulations | Descriptor for simulated series |

Both descriptors require `vertical_datum`, `unit=m`, `quantity=water_surface_elevation`, `raw_sha256` of the exact CSV and a nonempty unique `accepted_quality_flags` list. Datum names must match exactly and must not be unknown/unspecified/none. Relative gauge stage, discharge and other units/quantities are unsupported. Equal names and an evidence reference are supplied assertions, not an independently verified datum transformation.

The observation descriptor additionally requires `source_url`, `license`, `license_evidence`, `dataset_version` and offset-bearing `retrieved_at`. The simulation descriptor requires `model_name`, `model_version`, `run_id`, offset-bearing `generated_at` and `configuration_sha256`. That configuration hash is a supplied reference, not a checked configuration file in this tool. Production use requires retaining/verifying the actual configuration and all model inputs independently.

Limits: each CSV 10 MB, manifest 64,000 bytes, at most 100,000 expected station×time pairs and 100,000 rows per file. File identities are checked against descriptor hashes. CLI output adds the exact manifest hash. Raw-file hashes/source-line metadata allow original observations to be traced; this comparison report does not replace source archives.

## Metrics and interpretation
For each accepted pair define `error = simulated − observed`, in metres. With n paired errors:

- MAE = sum(abs(error)) / n.
- RMSE = sqrt(sum(error²) / n).
- Bias = sum(error) / n; positive means simulated elevation is higher on average.
- Maximum absolute error = max(abs(error)).

At least two accepted pairs are required; otherwise metrics are null. Station reports expose expected/accepted counts, absent/quarantined counts for each series, completeness and metric scope. Incomplete series can still report `accepted_pairs_only_incomplete_window` metrics, which are explicitly provisional and may be biased by missing-data selection. No confidence interval is invented. `comparison_complete` means every expected pair was accepted, not that errors meet a scientific standard.

Pooled metrics weight all accepted station/time pairs equally; they are not an average of per-station metrics and can be dominated by stations with more accepted pairs. Do not compare pooled metrics across different coverage without considering missingness. Large non-finite arithmetic errors cause rejection rather than invalid JSON numbers. No calibration or threshold optimization is performed.

Declared event-ID disjointness does not establish true event independence or prevent undeclared reuse of validation data. The report always states `scientific_validation=not_certified`, `acceptance_decision=not_assessed_no_thresholds_or_reviewer` and declared independence only. A reviewer must establish station representation, held-out events, uncertainty, source quality and suitable acceptance criteria before accepting a model. Station water-level errors alone do not validate flood extent, depth at properties, flood duration, barrier/drainage behavior or public risk classifications. This output is not automatically signed or converted into schema-v2 model-validation evidence.
