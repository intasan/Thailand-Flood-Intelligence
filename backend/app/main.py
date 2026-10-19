from datetime import datetime, timezone
import os
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from shapely.geometry import shape
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Thailand Flood Intelligence Research API", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

class PointRequest(BaseModel):
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lon: float = Field(ge=-180, le=180, allow_inf_nan=False)

class ParcelRequest(BaseModel):
    geometry: dict

def assessment(lat, lon):
    # No validated coverage has been imported. A coordinate is not evidence of safety.
    return {"location": {"lat": lat, "lon": lon, "crs": "EPSG:4326"},
        "status": "unsupported", "elevation_m": None, "water_level_m": None,
        "flood_depth_m": None, "duration_hours": None, "risk": "unknown",
        "metadata": {"generated_at": datetime.now(timezone.utc).isoformat(),
        "observed_at": None, "valid_at": None, "provenance": [], "model_version": None,
        "validation": {"status": "not_validated", "metrics": None},
        "vertical_datum": None, "resolution_m": None, "uncertainty": "not_quantified"},
        "limitations": ["ยังไม่มีข้อมูลและแบบจำลองที่ผ่านการตรวจสอบสำหรับพิกัดนี้", "ไม่มีข้อมูลไม่ได้หมายถึงไม่มีความเสี่ยง"]}

@app.get("/health/live")
def live(): return {"status": "alive"}

@app.get("/health/ready")
def ready():
    import psycopg
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=3) as c:
            c.execute("SELECT PostGIS_Version()")
            c.execute("SELECT 1 FROM sources LIMIT 1")
            c.execute("SELECT 1 FROM stations LIMIT 1")
            c.execute("SELECT 1 FROM observations LIMIT 1")
    except Exception:
        raise HTTPException(503, "PostGIS unavailable")
    return {"status": "ready"}

@app.get("/v1/status")
def status():
    from .repository import data_status
    try: result=data_status()
    except Exception: result={"database":"unavailable","observation_count":None,"station_count":None,"latest_observed_at":None}
    from .models import catalog
    models,rejected=catalog()
    return {**result,"validated_model_count":len(models),"rejected_model_count":rejected,"model_periods":[{"model_version":m["model_version"],"valid_from":m["valid_from"],"valid_to":m["valid_to"]} for _,m in models],"forecast_enabled":False}

@app.post("/v1/assess")
def assess(p: PointRequest): return assessment(p.lat, p.lon)

@app.post("/v1/parcels/assess")
def parcel(p: ParcelRequest):
    try:
        g = shape(p.geometry)
        if g.geom_type != "Polygon" or not g.is_valid or g.is_empty or sum(len(r.coords) for r in [g.exterior,*g.interiors])>1000:
            raise ValueError()
        if not all(-180 <= x <= 180 and -90 <= y <= 90 for ring in [g.exterior,*g.interiors] for x,y,*_ in ring.coords): raise ValueError()
        if g.has_z: raise ValueError()
    except Exception: raise HTTPException(422, "Valid 2D WGS84 Polygon required; maximum 1000 vertices")
    result=assessment(g.centroid.y,g.centroid.x)
    from pyproj import Geod
    area,perimeter=Geod(ellps="WGS84").geometry_area_perimeter(g)
    result["area_m2"]=abs(area)
    result["perimeter_m"]=perimeter
    result["geometry"]=p.geometry
    result["aggregation"]="unavailable; centroid is a display location, not parcel-wide analysis"
    return result

@app.get("/v1/geocode")
def geocode(q: str = Query(min_length=2, max_length=160)):
    from .providers import geocode as search, ProviderUnavailable
    try: return search(q)
    except (ProviderUnavailable, OSError, __import__("sqlite3").Error) as e: raise HTTPException(503, str(e))

@app.get("/v1/elevation")
def elevation(lat: float = Query(ge=-90,le=90,allow_inf_nan=False), lon: float = Query(ge=-180,le=180,allow_inf_nan=False)):
    from .providers import elevation as sample, ProviderUnavailable
    try: return sample(lat,lon)
    except (ProviderUnavailable, OSError, __import__("sqlite3").Error) as e: raise HTTPException(503,str(e))

@app.get("/v1/stations")
def stations(lat: float = Query(ge=-90,le=90,allow_inf_nan=False), lon: float = Query(ge=-180,le=180,allow_inf_nan=False), radius_km: float = Query(default=20,gt=0,le=100)):
    from .repository import nearby_stations
    try: return nearby_stations(lat,lon,radius_km)
    except Exception: raise HTTPException(503,"Station database unavailable")

@app.get("/v1/models/point")
def model_point(lat: float = Query(ge=-90,le=90,allow_inf_nan=False), lon: float = Query(ge=-180,le=180,allow_inf_nan=False), at: str | None = None):
    from .models import model_point as sample, ModelRejected, timestamp
    if at:
        try: timestamp(at)
        except ValueError:raise HTTPException(422,"Timezone-aware ISO8601 timestamp required")
    try: return sample(lat,lon,at)
    except ModelRejected:raise HTTPException(503,"Model output failed quality checks")
