from datetime import datetime, timezone
import os
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from shapely.geometry import shape
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Thailand Flood Intelligence Research API", version="0.1.0")
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
    except Exception:
        raise HTTPException(503, "PostGIS unavailable")
    return {"status": "ready"}

@app.get("/v1/status")
def status():
    return {"validated_model_count": 0, "observation_count": 0, "coverage": [], "forecast_enabled": False}

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
    result["geometry"]=p.geometry
    result["aggregation"]="unavailable; centroid is a display location, not parcel-wide analysis"
    return result

@app.get("/v1/geocode")
def geocode(q: str = Query(min_length=2, max_length=160)):
    # A contracted/self-hosted geocoder is intentionally required. No public-service autocomplete.
    raise HTTPException(503, "Place-name provider is not configured. Use coordinates, GPS or map click.")
