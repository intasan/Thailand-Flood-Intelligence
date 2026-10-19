from fastapi.testclient import TestClient
from app.main import app
from app.quality import validate_observation, route_order
import pytest
c=TestClient(app)

def test_missing_data_never_means_safe():
    r=c.post("/v1/assess",json={"lat":13.75,"lon":100.5}).json()
    assert r["risk"]=="unknown" and r["flood_depth_m"] is None
    assert r["metadata"]["validation"]["status"]=="not_validated"

@pytest.mark.parametrize("p", [{"lat":91,"lon":100},{"lat":13,"lon":181},{"lat":"nan","lon":100}])
def test_bad_coordinates(p): assert c.post("/v1/assess",json=p).status_code==422

def test_polygon():
    g={"type":"Polygon","coordinates":[[[100,13],[101,13],[101,14],[100,13]]]}
    assert c.post("/v1/parcels/assess",json={"geometry":g}).json()["risk"]=="unknown"

def test_self_intersection():
    g={"type":"Polygon","coordinates":[[[100,13],[101,14],[100,14],[101,13],[100,13]]]}
    assert c.post("/v1/parcels/assess",json={"geometry":g}).status_code==422

def test_geocoder_explicit_failure(monkeypatch):
    monkeypatch.setenv("PUBLIC_DATA_ENABLED","false")
    assert c.get("/v1/geocode?q=Bangkok").status_code==503

def test_observation_rejects_missing_datum():
    with pytest.raises(ValueError): validate_observation({"value":1})

def test_network_order_and_cycle():
    assert route_order([("up","mid"),("mid","down")])==["up","mid","down"]
    with pytest.raises(ValueError): route_order([("a","b"),("b","a")])

def test_readiness_not_liveness():
    assert c.get("/health/live").status_code==200
    assert c.get("/health/ready").status_code==503
