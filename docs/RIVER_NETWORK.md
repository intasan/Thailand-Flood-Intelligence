# Directed river-network preflight (audit v1.0.0)

This offline operator tool checks a submitted directed network before any hydraulic model is selected or run. It does not provide flood forecasts or hydraulic routing. No Thai river dataset is bundled or registered. Test fixtures are synthetic and remain in tests only.

## Run
From `backend/`, after installing requirements:

```bash
python -m app.river_network /path/to/network.json --raw-source /path/to/original-source-file --tolerance-m 30 > /path/to/network-audit.json
```

The command returns 0 with a JSON report only if structural checks and the original-source SHA256 match pass. Rejection returns 2, with a reason on stderr and no report on stdout. Shell redirection may create an empty output file on failure; only accept output after a zero exit status. No database or external service is changed. The original source is hashed locally in chunks; nothing is downloaded. Operators must preserve the actual original file and conversion method. Matching a supplied hash proves file identity, not authenticity or permission.

## Input contract

| Field | Required value / meaning |
|---|---|
| schema_version | Integer 1 |
| crs | EPSG:4326 |
| provenance.source_url | Original dataset reference |
| provenance.license | Published licence identity; never guess rights |
| provenance.license_evidence | Reference to the actual permission evidence |
| provenance.retrieved_at | Offset-bearing ISO8601 timestamp |
| provenance.dataset_version | Source release identity |
| provenance.raw_sha256 | Lowercase 64-character SHA256 of the original source file |
| provenance.direction_evidence | Reference explaining how flow direction was established |
| reaches | 1–10,000 reach objects |
| reaches[].id | Unique nonempty string, maximum 100 characters |
| reaches[].downstream_id | Existing reach ID, or explicit null for a dataset outlet |
| reaches[].geometry | 2D WGS84 GeoJSON LineString; coordinates ordered upstream to downstream |
| reaches[].incremental_catchment_area_m2 | Nonnegative finite incremental area, or missing/null if unknown |

Package size is limited to 20 MB, with at most 200,000 coordinate positions. Every downstream endpoint must be within the configured geodesic distance of the next reach's start. Default tolerance is 30 m, configurable from 0 to 1,000 m; this is a software tolerance, not a surveyed-accuracy claim. No snapping or automatic reversal occurs. Explicit outlet nulls prevent accidental missing links from being treated as valid outlets. Multiple outlets are reported separately, not joined artificially. The tool cannot establish whether a declared outlet is a true basin outlet or only the boundary of supplied coverage.

The graph must be acyclic, with only one downstream reach per reach. Duplicate IDs, missing/self downstream references, cycles, zero-length/invalid geometries and invalid numbers are rejected. Tidal reversals, bifurcations, canals with multiple outflows and backwater require a different representation and solver. A junction on the interior of another LineString must first be split into correctly directed reaches by the data operator.

## Interpretation
`topological_order` gives upstream-before-downstream order. `upstream_ids`, `length_m` (WGS84 ellipsoidal) and outlets describe the submitted network. `contributing_area_m2` sums each reach's incremental area and its upstream totals. The calculation assumes incremental catchments are mutually disjoint; no catchment polygons are supplied, so overlap cannot be checked. Do not supply already cumulative catchment areas as incremental areas. Any unknown area propagates downstream as null; it is never replaced with zero. Known zero remains valid. No discharge is inferred from area.

`status=structural_checks_passed` means structural checks only. `hydraulic_validation=not_performed` is mandatory. Direct Python calls to `audit_network` return `raw_source_checksum=not_checked`; only the CLI compares the raw file and changes this to `matched`. The CLI also records the exact submitted package hash, audit version and report-generation time. Report time is not source measurement time. Source rights and flow-direction evidence remain supplied assertions requiring human review.

Before operational use, a pilot still needs independently checked topology/coverage and permissions, surveyed terrain/channel sections and datum alignment, hydrographs and boundary conditions, rainfall/runoff and tide where relevant, barriers and drainage, an appropriate calibrated 1D/2D solver and held-out event validation. This tool makes no statement about whether water can reach a property. No network is exposed in the public Dashboard or registered as validated model coverage by this command.
