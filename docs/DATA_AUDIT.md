# Source audit — 2026-10-19 UTC
This is a desktop documentation review. No dataset downloaded, license agreement accepted, or station datum verified. `pending` means blocked from operational use.

| Dataset / service | Evidence | Resolution / datum | Decision |
|---|---|---|---|
| OSM raster tiles | https://operations.osmfoundation.org/policies/tiles/ | Basemap only; not terrain elevation | Interactive low-volume default, attribution shown. No bulk/offline download. Contracted provider required at scale. |
| Nominatim | https://operations.osmfoundation.org/policies/nominatim/ | Geocoding; no vertical datum | Not connected. No autocomplete or uncontrolled public requests. |
| Copernicus DEM GLO-30 | https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM | Approx. 30 m DSM, EGM2008; not surveyed bare-earth DTM | Pending actual download license/access review. Cannot resolve house, culvert or levee elevation reliably. |
| Copernicus view service | https://dataspace.copernicus.eu/news/2026-8-25-copernicus-dem-30m-view-service-update | Service-specific access restrictions | Do not assume free dataset license grants unrestricted view-service use. |
| ThaiWater | https://standard.thaiwater.net/ and https://www.thaiwater.net/ | Per-station frequency, QC and datum must be obtained | API standard is not a grant of credentials or redistribution rights. Pending agency permission and sample contract. |
| HEC-RAS 2D | https://www.hec.usace.army.mil/software/hec-ras/documentation/HEC-RAS_2D_Users_Manual_v6.6.pdf | Requires terrain, initial/boundary and meteorological conditions | Candidate only, solver not integrated. |

Additional required inputs: RID discharge and operations, TMD/radar rainfall, tide gauges, hydrographic network, local DTM/cross-sections, road crest elevations, levees, culverts, drainage and independent flood observations. Their rights, actual spatial/temporal resolution and vertical reference remain unverified. Never assume Thai station gauge zero equals MSL or EGM2008. Store explicit transformations and survey evidence.

## v0.2 update
- Open-Meteo Geocoding API (https://open-meteo.com/en/docs/geocoding-api): GeoNames location data, countryCode=TH, Thai localization, submitted queries only. Provides settlements/postcodes, not guaranteed house addresses. No Nominatim connection.
- Open-Meteo Elevation API (https://open-meteo.com/en/docs/elevation-api): Copernicus 2021 GLO-90, approximately 90 m surface elevation. Provider fetch timestamp is distinct from dataset release and observation time. Source vertical reference EGM2008 follows the Copernicus handbook, not a verified Thai station transformation.
- Free API is non-commercial only (https://open-meteo.com/en/terms); CC-BY attribution displayed. A contracted/commercial provider is required for commercial operation. Quota and cache are implemented, not unlimited API use.
- Live smoke calls successfully retrieved Bangkok location candidates and an elevation response for 13.75,100.5. A response is source connectivity evidence, not local accuracy validation or a flood forecast.

## HII archive verified in v0.3
Official catalog `water-level` / dataset ID `334aa20b-8187-430a-b8c5-d924f37334fe`; source root https://tiservice.hii.or.th/opendata/data_catalog/water_level/. Catalogue licence: Creative Commons Attribution Non-Commercial; no version supplied. Catalog says 10-minute MSL observations and monthly publication. Sentinel values are explicitly documented. Quality flag N=Normal is documented in Thaiwater Standard's quality flags page.

Canonical metadata and CPY001 September 2026 CSV were downloaded and parsed. The source contains 4,320 rows: 4,304 N-flag rows accepted and 16 non-N rows quarantined. Detailed checksums and coordinates are in HII_ARCHIVE_AUDIT.json. Raw archive data is not bundled into source code and is never represented as current observations. Timestamp zone and station-to-EGM2008 datum ties are unverified. The data-audit candidate is not a calibrated hydraulic pilot.

## v0.4 source freshness check
The official October 2026 archive directory https://tiservice.hii.or.th/opendata/data_catalog/water_level/2026/202610/ returned HTTP 200 with no CSV links at inspection on 2026-10-19 UTC. This is a point-in-time check, not a claim that no agency has live data. The licensed catalog still describes monthly archive publication; 10-minute measurement cadence does not imply live API availability. No separately licensed/verified live station adapter was identified or enabled in this increment. The platform reports `live=not_configured` rather than silently promoting historical records to current conditions.
