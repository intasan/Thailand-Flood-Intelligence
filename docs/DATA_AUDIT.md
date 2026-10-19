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
