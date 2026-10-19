# Pilot readiness — CPY001 data-audit candidate

Candidate source: HII station CPY001, สะพานเดชาติวงศ์, Nakhon Sawan, coordinates as published in canonical station metadata. This is a data-onboarding candidate, not a selected/calibrated hydraulic model domain. Station availability alone does not prove an appropriate floodplain pilot.

## Verified
- Official government catalog and non-commercial attribution licence inspected.
- Canonical station metadata and September 2026 water-level archive downloaded, hashed and parsed.
- 4,320 source records: 4,304 normal-flag records accepted, 16 unknown/non-normal records quarantined. No missing values replaced with zero.
- Source datum described as MSL. No verified transformation to EGM2008.
- Source CSV contains no timezone offset. Asia/Bangkok is an explicit operator assumption retained in provenance.

## Required before model construction

| Input / evidence | Required content | Current state |
|---|---|---|
| Station survey/datum tie | Gauge zero, survey benchmark, MSL realization, offsets, survey date/accuracy and transformation to model datum | Missing |
| Timestamp confirmation | Source agency timezone and definition of measurement timestamps | Unverified |
| Discharge / rating curves | Q–H relationship, validity periods, flow measurements, backwater/tide limitations | Missing |
| River geometry | Surveyed cross-sections/bathymetry, chainage, connected reaches and junctions, structures | Missing |
| Floodplain DTM | Bare-earth elevations, vertical datum, horizontal CRS, resolution, accuracy and licence | Missing; 90 m DSM is not a substitute |
| Roads / barriers / drainage | Crest elevations, levees, culverts, gates, pumps and operational time series | Missing |
| Upstream boundaries | Time-aligned inflow hydrographs at each modeled river boundary | Missing |
| Downstream boundaries | Stage/tide hydrograph and sensitivity to backwater for the chosen domain | Missing |
| Rainfall / losses | Validated rain series or radar with units, intervals, QC, catchments, infiltration assumptions | Missing |
| Calibration evidence | Identified event, measured stage/discharge, flood extent/depth/timing observations and uncertainty | Not selected |
| Independent validation | Different event and independent measured/reference observations | Not selected |
| Acceptance and review | Pre-agreed stage RMSE/bias, extent CSI, depth/timing error, mass balance, mesh/time-step convergence and reviewer sign-off | Not established |

## Gate
Do not generate operational flood depth, duration or property risk from this archive alone. The Research API retains explicit unknown outcomes. A qualified reviewer must first confirm the domain, source rights, datum/time alignment, boundary conditions, structures and independent event evidence. Software package approval fields are not a replacement for this review.

The repository can now onboard historical stage data and inspect gaps. Remaining prerequisites above are actual missing inputs, not placeholders to be filled with synthetic measurements. Test-only numerical fixtures must never be moved into operational model directories.
