"""Synthetic, ephemeral evidence fixtures only. No production signing keys or model data."""
import base64,hashlib,json
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from app.model_evidence import canonical_manifest,file_sha256
from app.models import validate_manifest,model_point,ModelRejected


def seal(p,m,key):
    inputs=p.parent/'inputs.json';report=p.parent/'validation.json'
    inputs.write_text(json.dumps({'inputs':m['input_provenance']}))
    report.write_text(json.dumps({k:v for k,v in m['validation'].items() if k!='report_sha256'}))
    m['input_manifest_sha256']=file_sha256(inputs);m['validation']['report_sha256']=file_sha256(report)
    m['evidence']={'input_manifest':{'path':inputs.name,'sha256':file_sha256(inputs)},'validation_report':{'path':report.name,'sha256':file_sha256(report)}}
    m['review_signature']=base64.b64encode(key.sign(canonical_manifest(m))).decode()
    p.write_text(json.dumps(m))

@pytest.fixture
def package(tmp_path,monkeypatch):
    model_root=tmp_path/'models';root=model_root/'test_only';root.mkdir(parents=True);r=root/'depth.tif'
    with rasterio.open(r,'w',driver='GTiff',width=2,height=2,count=1,dtype='float32',crs='EPSG:4326',transform=from_origin(100,14,.01,.01),nodata=-9999) as ds:
        ds.write(np.array([[.5,-9999],[0,1]],dtype='float32'),1);ds.update_tags(vertical_datum='TEST')
    key=Ed25519PrivateKey.generate();reviewers=tmp_path/'reviewers.json'
    reviewers.write_text(json.dumps({'reviewers':{'TEST_KEY':{'public_key_base64':base64.b64encode(key.public_key().public_bytes_raw()).decode(),'reviewer_id':'TEST','revoked':False}}}))
    monkeypatch.setenv('MODEL_DIRECTORY',str(model_root));monkeypatch.setenv('MODEL_REVIEWERS_FILE',str(reviewers))
    m={'schema_version':2,'review_key_id':'TEST_KEY','horizontal_crs':'EPSG:4326','resolution_native':[.01,.01],
       'model_version':'TEST_ONLY','solver':'TEST_FIXTURE_NOT_OPERATIONAL','vertical_datum':'TEST','input_manifest_sha256':'pending','generated_at':'2020-01-01T00:00:00Z','valid_from':'2020-01-01T00:00:00Z','valid_to':'2020-01-02T00:00:00Z','resolution_m':1000,'uncertainty':{'status':'test only'},'depth_semantics':'maximum_over_valid_interval','input_provenance':[{'license_evidence':'test','sha256':'0'*64}],
       'validation':{'status':'approved','reviewed_by':'TEST','report_sha256':'pending','reviewed_at':'2020-01-01T00:00:00Z','calibration_event':'TEST_A','validation_event':'TEST_B','metrics':{'stage_rmse_m':.1,'extent_csi':.9,'volume_error_fraction':.01},'acceptance_limits':{'stage_rmse_m':.2,'extent_csi':.8,'volume_error_fraction':.05},**{k:True for k in ['datum_ties_verified','river_network_verified','boundary_conditions_verified','structures_reviewed','mesh_convergence_passed']}},
       'assets':{'max_depth':{'path':'depth.tif','unit':'m','sha256':file_sha256(r)}}}
    p=root/'manifest.json';seal(p,m,key);return p,m,key

def test_validation_rejects_failed_metrics(package):
    p,m,key=package;m['validation']['metrics']['extent_csi']=.5;seal(p,m,key)
    with pytest.raises(ModelRejected):validate_manifest(p)

def test_checksum_rejected(package):
    p,m,key=package;m['assets']['max_depth']['sha256']='0'*64;seal(p,m,key)
    with pytest.raises(ModelRejected):validate_manifest(p)

def test_time_coverage_nodata_and_real_zero(package):
    assert model_point(13.995,100.005,'2020-01-01T12:00:00Z')['flood_depth_m']==.5
    assert model_point(13.985,100.005,'2020-01-01T12:00:00Z')['flood_depth_m']==0
    assert model_point(13.995,100.015,'2020-01-01T12:00:00Z')['status']=='unsupported'
    assert model_point(13.995,100.005,'2026-01-01T00:00:00Z')['status']=='unsupported'

def test_no_naive_datetime(package):
    with pytest.raises(ModelRejected):model_point(13,100,'2020-01-01')

def test_manifest_tampering_rejected(package):
    p,m,key=package;m['solver']='TAMPERED';p.write_text(json.dumps(m))
    with pytest.raises(ModelRejected):validate_manifest(p)

def test_untrusted_signer_rejected(package):
    p,m,_=package;seal(p,m,Ed25519PrivateKey.generate())
    with pytest.raises(ModelRejected):validate_manifest(p)

def test_revoked_reviewer_rejected(package,monkeypatch):
    import os
    from pathlib import Path
    p,_,_=package;r=Path(os.environ['MODEL_REVIEWERS_FILE']);d=json.loads(r.read_text());d['reviewers']['TEST_KEY']['revoked']=True;r.write_text(json.dumps(d))
    with pytest.raises(ModelRejected):validate_manifest(p)

def test_missing_evidence_rejected(package):
    p,_,_=package;(p.parent/'validation.json').unlink()
    with pytest.raises(ModelRejected):validate_manifest(p)

def test_modified_evidence_rejected(package):
    p,_,_=package;r=p.parent/'validation.json';r.write_text(r.read_text()+' ')
    with pytest.raises(ModelRejected):validate_manifest(p)

def test_negative_raster_cell_rejected_even_away_from_query(package):
    p,m,key=package;r=p.parent/'depth.tif'
    with rasterio.open(r,'r+') as ds:
        ds.write(np.array([[.5,-9999],[0,-1]],dtype='float32'),1)
    m['assets']['max_depth']['sha256']=file_sha256(r);seal(p,m,key)
    with pytest.raises(ModelRejected):validate_manifest(p)

def test_no_trust_store_inside_packages(package,monkeypatch):
    p,_,_=package;monkeypatch.setenv('MODEL_REVIEWERS_FILE',str(p.parent/'reviewers.json'))
    with pytest.raises(ModelRejected):validate_manifest(p)

def test_depth_duration_grid_mismatch_rejected(package):
    p,m,key=package;r=p.parent/'duration.tif'
    with rasterio.open(r,'w',driver='GTiff',width=2,height=2,count=1,dtype='float32',crs='EPSG:4326',transform=from_origin(100.005,14,.01,.01),nodata=-9999) as ds:
        ds.write(np.ones((2,2),dtype='float32'),1);ds.update_tags(vertical_datum='TEST')
    m['assets']['duration']={'path':r.name,'sha256':file_sha256(r),'unit':'h'};seal(p,m,key)
    with pytest.raises(ModelRejected):validate_manifest(p)

def test_version_one_self_approval_rejected(package):
    p,m,_=package;m['schema_version']=1;m.pop('review_signature');p.write_text(json.dumps(m))
    with pytest.raises(ModelRejected):validate_manifest(p)

def test_duplicate_json_keys_rejected(package):
    p,_,_=package;s=p.read_text();p.write_text('{"schema_version":2,'+s[1:])
    with pytest.raises(ModelRejected):validate_manifest(p)

def test_raster_datum_mismatch_rejected(package):
    p,m,key=package;r=p.parent/'depth.tif'
    with rasterio.open(r,'r+') as ds:ds.update_tags(vertical_datum='OTHER')
    m['assets']['max_depth']['sha256']=file_sha256(r);seal(p,m,key)
    with pytest.raises(ModelRejected):validate_manifest(p)
