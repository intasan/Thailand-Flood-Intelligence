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

def test_database_unavailable_is_not_zero_count(monkeypatch):
    monkeypatch.delenv('DATABASE_URL',raising=False)
    result=c.get('/v1/status').json()
    assert result['database']=='unavailable' and result['observation_count'] is None

def test_geodesic_parcel_area():
    g={'type':'Polygon','coordinates':[[[100,13],[100.001,13],[100.001,13.001],[100,13.001],[100,13]]]}
    result=c.post('/v1/parcels/assess',json={'geometry':g}).json()
    assert 11000<result['area_m2']<13000 and result['risk']=='unknown'

def test_model_unknown_without_files(tmp_path,monkeypatch):
    monkeypatch.setenv('MODEL_DIRECTORY',str(tmp_path))
    result=c.get('/v1/models/point?lat=13&lon=100').json()
    assert result['status']=='unsupported' and result['flood_depth_m'] is None

def test_readiness_never_claims_live_feed_or_property_risk(monkeypatch,tmp_path):
    monkeypatch.delenv('DATABASE_URL',raising=False)
    monkeypatch.setenv('MODEL_DIRECTORY',str(tmp_path))
    result=c.get('/v1/readiness').json()
    statuses={r['id']:r['status'] for r in result['steps']}
    assert statuses['live']=='not_configured' and statuses['risk']=='not_enabled'
    assert statuses['archive']=='unknown_database_unavailable'
    assert result['review_signature_required'] is True

def test_concave_parcel_display_point_is_inside():
    from shapely.geometry import shape,Point
    geometry={'type':'Polygon','coordinates':[[[100,13],[100.03,13],[100.03,13.01],[100.01,13.01],[100.01,13.03],[100,13.03],[100,13]]]}
    polygon=shape(geometry)
    assert not polygon.covers(polygon.centroid)
    result=c.post('/v1/parcels/assess',json={'geometry':geometry}).json()
    assert polygon.covers(Point(result['location']['lon'],result['location']['lat']))
    assert result['risk']=='unknown'

def test_hole_area_is_independent_of_ring_direction():
    outer=[[100,13],[100.03,13],[100.03,13.03],[100,13.03],[100,13]]
    hole=[[100.01,13.01],[100.02,13.01],[100.02,13.02],[100.01,13.02],[100.01,13.01]]
    a=c.post('/v1/parcels/assess',json={'geometry':{'type':'Polygon','coordinates':[outer,hole]}}).json()
    b=c.post('/v1/parcels/assess',json={'geometry':{'type':'Polygon','coordinates':[outer,list(reversed(hole))]}}).json()
    whole=c.post('/v1/parcels/assess',json={'geometry':{'type':'Polygon','coordinates':[outer]}}).json()
    assert abs(a['area_m2']-b['area_m2'])<.01
    assert a['area_m2']<whole['area_m2']
    assert a['total_boundary_m']>a['perimeter_m']

def test_large_multibyte_request_rejected_before_geometry_processing():
    body='{"geometry":{},"padding":"'+'ก'*22000+'"}'
    assert c.post('/v1/parcels/assess',content=body.encode(),headers={'Content-Type':'application/json'}).status_code==413

def test_whitespace_search_is_invalid_before_provider_request():
    assert c.get('/v1/geocode?q=%20%20').status_code==422
