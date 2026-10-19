# Local DEM integrity audit v1.0.0

Operator-only preprocessing for a self-contained elevation GeoTIFF. This checks the supplied file and declared metadata; it does not certify survey accuracy, establish pilot coverage or approve a hydraulic model. No real DEM is bundled or imported by this feature. Synthetic rasters exist only in tests.

## Run
From `backend/` with requirements installed:

```bash
python -m app.dem_audit /path/to/elevation.tif /path/to/dem-manifest.json > /path/to/dem-audit.json
```

Exit 0 emits JSON; exit 2 rejects input with stderr and no report on stdout. A zero exit status means integrity checks passed, not usable model terrain: read `coverage_status`, `invalid_fraction`, `datum_alignment` and the limitations. Header/metadata validity can pass even when all pixels are missing, in which case `coverage_status=no_usable_pixels` and both elevation extrema are null. Shell redirection may leave an empty output on rejection. No database, public API or external resource is modified.

## Manifest contract

| Field | Requirement |
|---|---|
| schema_version | Integer 1 |
| source_url, license, license_evidence | Actual original source and permission references |
| dataset_version, retrieved_at | Source release and offset-bearing ISO8601 retrieval timestamp |
| raw_sha256 | SHA256 of exact local GeoTIFF bytes |
| unit | `m`, for elevation values |
| terrain_type | `DTM` or `DSM`; supplied assertion requiring source review |
| vertical_datum | Explicit named datum; not unknown/unspecified/none |
| vertical_datum_evidence | Reference proving the source datum convention |
| horizontal_crs | CRS definition matching the raster CRS |
| pixel_size_native_units | Two positive finite values matching actual raster pixel spacing |

File checksum identity and metadata presence do not authenticate licence rights, source identity or accuracy. A named vertical datum is not evidence of alignment to gauges or another DEM. No offset or datum transformation is guessed. Survey/benchmark evidence and the actual transformation pipeline must be independently assessed before any water-surface comparison.

## Raster checks and outputs
Only local `.tif`/`.tiff` single-band real numeric GTiff files with a known CRS, finite north-up affine grid, identity scale and zero offset are supported. External masks/sidecars are rejected so a single file hash covers the audited raster inputs; produce a self-contained GeoTIFF explicitly and retain its conversion provenance. Rotated/south-up grids and scaled values require an explicit documented normalization step outside this tool. The audit does not warp, repair or alter files. A raster elevation-unit tag that contradicts metre units, or a VERTICAL_DATUM tag that contradicts the manifest, is rejected. Missing raster tags do not independently confirm manifest assertions.

Limits: 2 GB file, 100 million pixels, 64,000-byte manifest. Read windows are at most 512×512 pixels, including edge windows. All pixels are scanned, not sampled. Report counts distinguish masked pixels from unmasked non-finite values. Invalid fraction is their sum divided by all grid pixels. Elevation min/max use only finite unmasked pixels; zero and negative elevations remain valid. NaN/Infinity NoData metadata is represented as JSON null with `nodata_value_nonfinite=true`, never invalid JSON numbers.

Bounds and pixel size are reported in native coordinate units, with horizontal axis unit names. `pixel_size_m` is populated only for projected metre grids. Geographic degree grids, or grids in other native units, retain native resolution and `pixel_size_m=null`; no constant metre resolution is inferred. Pixel spacing is not spatial accuracy.

Coverage status is `complete_grid`, `partial_grid` or `no_usable_pixels`. It refers only to the file's grid, not a whole river basin, pilot study boundary, property or hydrologically connected area. The tool does not inspect independent basin footprints, drainage structures, roads/levees, channel bathymetry or connectivity. A complete DSM may still contain buildings and vegetation and is not a surveyed bare-earth terrain model. A DTM label also requires verification.

Output records exact raster and manifest hashes, audit version, generated time and original provenance. `datum_alignment=not_verified`, `accuracy_status=not_independently_validated` and `hydraulic_validation=not_performed` remain explicit. No datum reconciliation, rainfall/runoff transformation, routing, inundation or property-risk estimate is performed. No arbitrary minimum DEM resolution or accuracy threshold is treated as a universal hydrologic acceptance criterion.
