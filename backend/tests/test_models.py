import hashlib,json
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from app.models import validate_manifest,model_point,ModelRejected

@pytest.fixture
def package(tmp_path,monkeypatch):
    root=tmp_path/'test_only';root.mkdir();r=root/'depth.tif'
    with rasterio.open(r,'w',driver='GTiff',width=2,height=2,count=1,dtype='float32',crs='EPSG:4326',transform=from_origin(100,14,.01,.01),nodata=-9999) as ds:
        ds.write(np.array([[.5,-9999],[0,1]],dtype='float32'),1)
    m={'model_version':'TEST_ONLY','solver':'TEST_FIXTURE_NOT_OPERATIONAL','vertical_datum':'TEST','input_manifest_sha256':'test','generated_at':'2020-01-01T00:00:00Z','valid_from':'2020-01-01T00:00:00Z','valid_to':'2020-01-02T00:00:00Z','resolution_m':1000,'uncertainty':{'status':'test only'},'depth_semantics':'maximum_over_valid_interval','input_provenance':[{'license_evidence':'test','sha256':'test'}],
       'validation':{'status':'approved','reviewed_by':'TEST','report_sha256':'test','reviewed_at':'2020-01-01T00:00:00Z','calibration_event':'TEST_A','validation_event':'TEST_B','metrics':{'stage_rmse_m':.1,'extent_csi':.9,'volume_error_fraction':.01},'acceptance_limits':{'stage_rmse_m':.2,'extent_csi':.8,'volume_error_fraction':.05},**{k:True for k in ['datum_ties_verified','river_network_verified','boundary_conditions_verified','structures_reviewed','mesh_convergence_passed']}},
       'assets':{'max_depth':{'path':'depth.tif','unit':'m','sha256':hashlib.sha256(r.read_bytes()).hexdigest()}}}
    p=root/'manifest.json';p.write_text(json.dumps(m));monkeypatch.setenv('MODEL_DIRECTORY',str(tmp_path));return p,m

def test_validation_rejects_failed_metrics(package):
    p,m=package;m['validation']['metrics']['extent_csi']=.5;p.write_text(json.dumps(m))
    with pytest.raises(ModelRejected):validate_manifest(p)

def test_checksum_rejected(package):
    p,m=package;m['assets']['max_depth']['sha256']='bad';p.write_text(json.dumps(m))
    with pytest.raises(ModelRejected):validate_manifest(p)

def test_time_coverage_nodata_and_real_zero(package):
    assert model_point(13.995,100.005,'2020-01-01T12:00:00Z')['flood_depth_m']==.5
    assert model_point(13.985,100.005,'2020-01-01T12:00:00Z')['flood_depth_m']==0
    assert model_point(13.995,100.015,'2020-01-01T12:00:00Z')['status']=='unsupported'
    assert model_point(13.995,100.005,'2026-01-01T00:00:00Z')['status']=='unsupported'

def test_no_naive_datetime(package):
    with pytest.raises(ModelRejected):model_point(13,100,'2020-01-01')
