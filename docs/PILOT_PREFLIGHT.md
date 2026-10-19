# Integrated pilot input preflight v1.0.0

One read-only command checks a consistent local network/catchment, historical rainfall and DEM input bundle. It recomputes checks from original inputs rather than trusting previously generated audit reports. No real pilot inputs are shipped and all test bundles are synthetic. This does not register a pilot, approve a model or enable public risk results.

## Run
From `backend/` with requirements installed:

```bash
python -m app.pilot_preflight /path/to/pilot/pilot.json > /path/to/pilot/preflight-report.json
```

Bundle JSON:

```json
{
  "schema_version": 1,
  "pilot_id": "your-study-identifier",
  "files": {
    "network": "network.json",
    "network_raw_source": "original-network-bundle.zip",
    "rainfall_csv": "rainfall.csv",
    "rainfall_manifest": "rainfall-manifest.json",
    "dem": "elevation.tif",
    "dem_manifest": "dem-manifest.json"
  }
}
```

These are filenames only, not sample observations. Supply actual approved source files following [RIVER_NETWORK.md](RIVER_NETWORK.md), [RAINFALL_INPUT.md](RAINFALL_INPUT.md) and [DEM_AUDIT.md](DEM_AUDIT.md). File paths must be relative, exist and resolve within the bundle directory. Absolute paths, directory traversal and symlinks escaping that directory are rejected. Subdirectories are permitted. Do not modify inputs during auditing. Source rights and the supplied evidence require independent human verification; checksums establish file identity only.

Exit 2 rejects malformed, mismatched or unsupported inputs with stderr and no report on stdout. Exit 0 emits a report which may still contain input gaps. Shell redirection can leave an empty file on rejection. No database writes, downloads, model execution or publication occur.

## Combined checks
- Revalidate directed topology and all incremental catchment polygons, including overlaps and reach coverage.
- Match the exact network JSON hash declared in the rainfall manifest, and hash the original network source bundle against its provenance.
- Verify rainfall CSV provenance/hash/unit/time-grid and each reach's interval completeness; no interpolation or missing-to-zero conversion.
- Verify the DEM original hash, CRS, vertical-datum declarations, native pixel spacing and full-grid valid/missing counts.
- Independently inspect DEM coverage for each submitted incremental catchment, distinguishing missing data inside the study geometry from missing pixels elsewhere in the raster.

Exact hashes for bundle, network, original network source, rainfall CSV/manifest and DEM/manifest are included. The report retains rainfall summaries/provenance but omits the potentially large observation-record array; the rainfall CLI can separately emit full normalized records. The network audit version and successful original-source checksum are recorded.

## DEM/catchment coverage method
WGS84 polygon edges are densified to at most 0.001° segment length before transformation to the raster CRS, with explicit x/y axis ordering. Transformed polygon bounds are checked against the north-up raster footprint. Within the footprint, bounded 512×512 windows count all pixels touched by the geometry and test their masks/finite values. Holes and MultiPolygon geometry are preserved. An entire catchment outside the raster has zero selected pixels and null missing-pixel fraction; it is not complete coverage. Partial footprint coverage fails even if every selected pixel is valid.

The method is an approximate regional geometry/pixel check, not a surveyed area calculation or proof of hydrologic connectivity. Boundary curvature is approximated at the declared densification scale; no metre-accuracy guarantee follows from that scale. `all_touched` deliberately includes boundary pixels, which can conservatively flag adjacent missing pixels at edges/hole boundaries. Counts and fractions describe touched pixels, not proportions of land area. Do not use this to infer property-level elevation, flow paths or flood accessibility. No nodata filling, snapping or reprojection of elevation values occurs.

Global work limits: at most 1,000,000 transformed geometry positions and 100,000,000 candidate raster pixel evaluations across all catchments. Existing per-input byte/row/pixel limits also apply. These limits cause rejection, never silent truncation. Subdivide a study deliberately if necessary and preserve its coverage definition.

## Status and blockers
`status=input_checks_passed` means there are no detected input blockers under these checks. `input_gaps_detected` identifies one or more of:

| Blocker | Meaning |
|---|---|
| rainfall_incomplete | An expected interval is absent or quarantined |
| dem_catchment_coverage_incomplete | A catchment extends outside the DEM, selects no pixels, or touches invalid pixels |
| bare_earth_terrain_not_established | The supplied terrain is labelled DSM rather than DTM |

A DTM label does not prove a bare-earth survey, resolution adequacy or datum correctness. `hydraulic_ready=false` and `hydraulic_validation=not_performed` remain true for every bundle. Separate scientific blockers record unverified survey/datum alignment, unregistered boundary hydrographs, unverified channel/barrier geometry, uncalibrated rainfall/runoff transformation and missing solver/independent event validation. These cannot be cleared by metadata assertions or passing software checks.

No reach discharge, water level, inundation extent/depth/duration, tide/drainage interaction or public property-risk result is computed. The public readiness API remains unchanged because a local input audit is not approved operational coverage.
