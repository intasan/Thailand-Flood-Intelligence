# Architecture and truthful scope
Browser (Next.js / MapLibre) → same-origin /api proxy → FastAPI → PostGIS.
Airflow audits approved source manifests. Future immutable raw storage → normalization → QA → observations → approved hydraulic runs → API. Current assessment endpoints deliberately do not query model tables: no imported/approved runs exist. No live observations, DEM samples or forecasts are served.

## Hydraulic decision record
Candidate: coupled river-network 1D + floodplain 2D shallow-water model (HEC-RAS), executed on a separate supported solver host, not inside this Docker stack. Final solver choice requires pilot data, licensing/runtime review and benchmarks. This is a design decision, not implemented simulation.
River flow must propagate upstream/downstream with boundary hydrographs, lateral rainfall/runoff, downstream tidal stage, surveyed bathymetry, roughness and structures. Levees, road embankments, culverts, gates and drainage determine connectivity. A DEM bathtub subtraction must never become public hazard depth. Topological sorting utility only validates acyclic river graphs; tidal loops need coupled treatment.

## Pilot gate
Choose a small surveyed river reach only after securing permissions, cross-sections, gauge datum ties, discharge/stage/rain/tide time series, DTM and structure survey. No pilot chosen merely from data availability assumptions.
Calibrate on one historical event; independently validate on another. Before evaluation, a hydrologist must approve metric thresholds for stage RMSE/bias, flood extent CSI, depth errors, arrival/recession timing, volume balance and mesh/time-step convergence. Archive raw checksums, solver version, parameters, boundary conditions, validation dates, reviewer and uncertainty ensemble. Test dry/wet transitions, barrier and culvert connectivity, tidal reversal and missing data. Reject stale or out-of-coverage output. Missing data must never map to low risk.

## Security and privacy
No server-side fetching of arbitrary Google URLs. GPS/parcel coordinates are sent only for requested assessment, not persisted by application code. Avoid coordinate request-body logging in deployment. Limit vertices/request size at a reverse proxy before public use. Public deployment additionally needs TLS, rate limiting, access control for ingestion, retention policy, backups and monitoring. Credentials remain environment-only.
