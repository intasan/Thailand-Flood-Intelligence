"""End-to-end synthetic pilot bundles only, not operational hydrology."""
from hashlib import sha256
import json
import subprocess
import sys
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from app.pilot_preflight import audit_pilot
from test_rainfall_input import inputs
from test_dem_audit import raster


def write_json(path,data):path.write_text(json.dumps(data))


def bundle(tmp_path):
    raw,m,n=inputs()
    source=tmp_path/'original.bin';source.write_bytes(b'SYNTHETIC_PILOT_ONLY')
    n['provenance']['raw_sha256']=sha256(source.read_bytes()).hexdigest()
    network=tmp_path/'network.json';write_json(network,n)
    m['network_package_sha256']=sha256(network.read_bytes()).hexdigest()
    (tmp_path/'rain.csv').write_bytes(raw);write_json(tmp_path/'rain.json',m)
    p,dm=raster(tmp_path,np.ones((60,70)),crs='EPSG:4326',transform=from_origin(99.97,15.03,.001,.001))
    dm['pixel_size_native_units']=[.001,.001];write_json(tmp_path/'dem.json',dm)
    config={'schema_version':1,'pilot_id':'SYNTHETIC_TEST_ONLY','files':{'network':'network.json','network_raw_source':'original.bin','rainfall_csv':'rain.csv','rainfall_manifest':'rain.json','dem':p.name,'dem_manifest':'dem.json'}}
    path=tmp_path/'pilot.json';write_json(path,config)
    return path


def change_dem(path,values):
    config=json.loads(path.read_text());root=path.parent
    raster_path=root/config['files']['dem'];metadata_path=root/config['files']['dem_manifest']
    with rasterio.open(raster_path,'r+') as ds:ds.write(values.astype('float32'),1)
    m=json.loads(metadata_path.read_text());m['raw_sha256']=sha256(raster_path.read_bytes()).hexdigest();write_json(metadata_path,m)


def test_full_bundle_integrity_never_claims_hydraulic_readiness(tmp_path):
    path=bundle(tmp_path);r=audit_pilot(path)
    assert r['status']=='input_checks_passed'
    assert r['input_blockers']==[] and r['hydraulic_ready'] is False
    assert r['hydraulic_validation']=='not_performed'
    assert len(r['scientific_blockers'])==5
    assert r['dem_catchment_coverage']['complete'] is True
    assert all(s['invalid_touched_pixels']==0 for s in r['dem_catchment_coverage']['catchments'])
    assert r['hashes']['bundle']==sha256(path.read_bytes()).hexdigest()
    assert r['network']['raw_source_checksum']=='matched'
    assert 'records' not in r['rainfall']
    assert 'flood_depth_m' not in r


def test_missing_rainfall_is_a_blocker_not_zero(tmp_path):
    path=bundle(tmp_path);raw=(tmp_path/'rain.csv').read_bytes().splitlines(keepends=True)
    new=b''.join(raw[:-1]);(tmp_path/'rain.csv').write_bytes(new)
    m=json.loads((tmp_path/'rain.json').read_text());m['raw_sha256']=sha256(new).hexdigest();write_json(tmp_path/'rain.json',m)
    r=audit_pilot(path)
    assert r['status']=='input_gaps_detected' and 'rainfall_incomplete' in r['input_blockers']
    assert r['rainfall']['summaries'][-1]['total_rainfall_mm'] is None


def test_nodata_inside_catchment_blocks_coverage(tmp_path):
    path=bundle(tmp_path);v=np.ones((60,70));v[15,35]=-9999;change_dem(path,v)
    r=audit_pilot(path)
    assert 'dem_catchment_coverage_incomplete' in r['input_blockers']
    b=next(c for c in r['dem_catchment_coverage']['catchments'] if c['reach_id']=='b')
    assert b['invalid_touched_pixels']==1


def test_nodata_outside_catchments_is_not_a_false_gap(tmp_path):
    path=bundle(tmp_path);v=np.ones((60,70));v[0,0]=-9999;change_dem(path,v)
    r=audit_pilot(path)
    assert r['dem']['coverage_status']=='partial_grid'
    assert r['dem_catchment_coverage']['complete'] is True
    assert r['status']=='input_checks_passed'


def test_outside_dem_reports_no_selected_pixels(tmp_path):
    path=bundle(tmp_path)
    p,dm=raster(tmp_path,np.ones((5,5)),crs='EPSG:4326',transform=from_origin(90,20,.001,.001))
    dm['pixel_size_native_units']=[.001,.001];write_json(tmp_path/'dem.json',dm)
    r=audit_pilot(path)
    assert 'dem_catchment_coverage_incomplete' in r['input_blockers']
    assert all(c['touched_pixels']==0 and c['invalid_touched_fraction'] is None for c in r['dem_catchment_coverage']['catchments'])


def test_projected_dem_transform_and_dsm_blocker(tmp_path):
    path=bundle(tmp_path)
    p,dm=raster(tmp_path,np.ones((100,100)),crs='EPSG:32647',transform=from_origin(600000,1670000,200,200))
    dm['pixel_size_native_units']=[200,200];dm['terrain_type']='DSM';write_json(tmp_path/'dem.json',dm)
    r=audit_pilot(path)
    assert r['dem_catchment_coverage']['complete'] is True
    assert 'bare_earth_terrain_not_established' in r['input_blockers']
    assert r['hydraulic_ready'] is False


@pytest.mark.parametrize('kind',['missing_file','absolute','escape','unknown_key','bad_schema','bad_id','source_hash','network_hash'])
def test_invalid_bundle_rejected(tmp_path,kind):
    path=bundle(tmp_path);cfg=json.loads(path.read_text())
    if kind=='missing_file':cfg['files']['dem']='missing.tif'
    if kind=='absolute':cfg['files']['network']=str(tmp_path/'network.json')
    if kind=='escape':cfg['files']['network']='../outside.json'
    if kind=='unknown_key':cfg['files']['extra']='network.json'
    if kind=='bad_schema':cfg['schema_version']=True
    if kind=='bad_id':cfg['pilot_id']=''
    if kind=='source_hash':(tmp_path/'original.bin').write_bytes(b'changed')
    if kind=='network_hash':(tmp_path/'network.json').write_text((tmp_path/'network.json').read_text()+' ')
    write_json(path,cfg)
    with pytest.raises(ValueError):audit_pilot(path)


def test_symlink_escape_rejected(tmp_path):
    root=tmp_path/'pilot';root.mkdir();path=bundle(root)
    outside=tmp_path/'outside.json';outside.write_text('{}')
    (root/'link.json').symlink_to(outside)
    cfg=json.loads(path.read_text());cfg['files']['network']='link.json';write_json(path,cfg)
    with pytest.raises(ValueError,match='inside'):audit_pilot(path)


def test_resource_limits_fail_closed(tmp_path,monkeypatch):
    import app.pilot_preflight as module
    path=bundle(tmp_path)
    monkeypatch.setattr(module,'MAX_COVERAGE_PIXELS',1)
    with pytest.raises(ValueError,match='pixel evaluation'):audit_pilot(path)
    monkeypatch.setattr(module,'MAX_COVERAGE_PIXELS',100000000)
    monkeypatch.setattr(module,'MAX_TRANSFORM_POSITIONS',1)
    with pytest.raises(ValueError,match='densification'):audit_pilot(path)


def test_cli_emits_report_or_rejects_without_success_stdout(tmp_path):
    path=bundle(tmp_path);cmd=[sys.executable,'-m','app.pilot_preflight',str(path)]
    r=subprocess.run(cmd,capture_output=True,text=True)
    assert r.returncode==0,r.stderr
    assert json.loads(r.stdout)['hydraulic_ready'] is False
    (tmp_path/'original.bin').write_bytes(b'changed')
    r=subprocess.run(cmd,capture_output=True,text=True)
    assert r.returncode==2 and not r.stdout


def test_partial_footprint_is_detected_even_with_valid_selected_pixels(tmp_path):
    path=bundle(tmp_path)
    p,dm=raster(tmp_path,np.ones((60,40)),crs='EPSG:4326',transform=from_origin(99.97,15.03,.001,.001))
    dm['pixel_size_native_units']=[.001,.001];write_json(tmp_path/'dem.json',dm)
    r=audit_pilot(path)
    b=next(c for c in r['dem_catchment_coverage']['catchments'] if c['reach_id']=='b')
    assert b['valid_touched_pixels']>0 and b['invalid_touched_pixels']==0
    assert b['within_raster_bounds'] is False
    assert 'dem_catchment_coverage_incomplete' in r['input_blockers']


def test_missing_pixels_inside_a_hole_are_not_false_coverage_gaps(tmp_path):
    from test_catchments import box
    path=bundle(tmp_path)
    n=json.loads((tmp_path/'network.json').read_text())
    n['reaches'][0]['incremental_catchment_geometry']['coordinates'].append(box(99.991,15.001,99.994,15.005))
    write_json(tmp_path/'network.json',n)
    m=json.loads((tmp_path/'rain.json').read_text());m['network_package_sha256']=sha256((tmp_path/'network.json').read_bytes()).hexdigest();write_json(tmp_path/'rain.json',m)
    values=np.ones((60,70));values[26,22]=-9999;change_dem(path,values)
    r=audit_pilot(path)
    assert r['dem']['invalid_fraction']>0
    assert r['status']=='input_checks_passed'
