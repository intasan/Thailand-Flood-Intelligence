"""Synthetic rasters only; no real terrain or surveyed elevations."""
from hashlib import sha256
import json
import subprocess
import sys
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin, Affine
from app.dem_audit import audit_dem


def raster(tmp_path,values=None,crs='EPSG:32647',nodata=-9999,transform=None,count=1):
    p=tmp_path/'TEST_ONLY.tif'
    values=np.array([[0,-2],[3,4]],dtype='float32') if values is None else np.asarray(values,dtype='float32')
    with rasterio.open(p,'w',driver='GTiff',width=values.shape[1],height=values.shape[0],count=count,dtype='float32',crs=crs,nodata=nodata,transform=transform or from_origin(500000,1700000,10,10)) as ds:
        for band in range(1,count+1):ds.write(values,band)
    m={'schema_version':1,'source_url':'https://example.invalid/TEST_ONLY','license':'TEST_ONLY',
       'license_evidence':'TEST_ONLY','dataset_version':'SYNTHETIC_TEST_ONLY','retrieved_at':'2020-01-01T00:00:00Z',
       'vertical_datum':'SYNTHETIC_TEST_ONLY','vertical_datum_evidence':'TEST_ONLY','horizontal_crs':crs or 'EPSG:32647',
       'unit':'m','terrain_type':'DTM','raw_sha256':sha256(p.read_bytes()).hexdigest(),
       'pixel_size_native_units':[10,10]}
    return p,m


def rehash(p,m):m['raw_sha256']=sha256(p.read_bytes()).hexdigest()


def test_complete_grid_zero_negative_and_metadata(tmp_path):
    p,m=raster(tmp_path);r=audit_dem(p,m)
    assert r['valid_pixels']==4 and r['invalid_fraction']==0
    assert r['min_elevation_m']==-2 and r['max_elevation_m']==4
    assert r['pixel_size_m']==[10,10]
    assert r['coverage_status']=='complete_grid'
    assert r['hydraulic_validation']=='not_performed'
    assert r['datum_alignment']=='not_verified'
    assert 'flood_depth_m' not in r


def test_masked_and_nonfinite_are_distinct(tmp_path):
    p,m=raster(tmp_path,[[0,-9999],[np.nan,np.inf]])
    r=audit_dem(p,m)
    assert r['valid_pixels']==1 and r['masked_pixels']==1 and r['unmasked_nonfinite_pixels']==2
    assert r['invalid_fraction']==.75
    assert r['min_elevation_m']==r['max_elevation_m']==0
    assert r['coverage_status']=='partial_grid'


def test_all_missing_is_not_usable_terrain(tmp_path):
    p,m=raster(tmp_path,[[-9999,-9999],[-9999,-9999]])
    r=audit_dem(p,m)
    assert r['coverage_status']=='no_usable_pixels'
    assert r['min_elevation_m'] is None and r['valid_pixels']==0


def test_geographic_pixels_are_not_reported_as_metres(tmp_path):
    p,m=raster(tmp_path,crs='EPSG:4326',transform=from_origin(100,15,.001,.001))
    m['pixel_size_native_units']=[.001,.001]
    r=audit_dem(p,m)
    assert r['pixel_size_m'] is None
    assert r['horizontal_axis_units']==['degree','degree']


@pytest.mark.parametrize('change',[
    lambda m:m.update(license_evidence=''),
    lambda m:m.update(vertical_datum='unknown'),
    lambda m:m.update(vertical_datum_evidence=''),
    lambda m:m.update(terrain_type='unknown'),
    lambda m:m.update(unit='ft'),
    lambda m:m.update(retrieved_at='2020-01-01'),
    lambda m:m.update(horizontal_crs='EPSG:4326'),
    lambda m:m.update(raw_sha256='0'*64),
    lambda m:m.update(pixel_size_native_units=[20,20]),
    lambda m:m.update(pixel_size_native_units=[True,10]),
    lambda m:m.update(schema_version=True),
])
def test_bad_manifest_rejected(tmp_path,change):
    p,m=raster(tmp_path);change(m)
    with pytest.raises(ValueError):audit_dem(p,m)


@pytest.mark.parametrize('mode',['rotation','south_up','no_crs','multiple_bands','scale','datum_tag','unit_tag','sidecar'])
def test_incompatible_raster_rejected(tmp_path,mode):
    kwargs={}
    if mode=='rotation':kwargs['transform']=Affine(10,1,500000,0,-10,1700000)
    if mode=='south_up':kwargs['transform']=Affine(10,0,500000,0,10,1700000)
    if mode=='no_crs':kwargs['crs']=None
    if mode=='multiple_bands':kwargs['count']=2
    p,m=raster(tmp_path,**kwargs)
    if mode in ('scale','datum_tag','unit_tag','sidecar'):
        with rasterio.Env(GDAL_TIFF_INTERNAL_MASK=False):
            with rasterio.open(p,'r+') as ds:
                if mode=='scale':ds.scales=(.1,)
                if mode=='datum_tag':ds.update_tags(VERTICAL_DATUM='DIFFERENT_TEST_DATUM')
                if mode=='unit_tag':ds.set_band_unit(1,'ft')
                if mode=='sidecar':ds.write_mask(np.array([[255,0],[255,255]],dtype='uint8'))
        rehash(p,m)
    with pytest.raises(ValueError):audit_dem(p,m)


def test_bounded_windows_cover_full_raster(tmp_path):
    values=np.ones((513,514),dtype='float32');values[-1,-1]=-9999
    p,m=raster(tmp_path,values)
    r=audit_dem(p,m)
    assert r['total_pixels']==513*514 and r['valid_pixels']==513*514-1
    assert r['masked_pixels']==1


def test_nan_nodata_serializes_as_json_null(tmp_path):
    p,m=raster(tmp_path,[[1,np.nan]],nodata=np.nan)
    r=audit_dem(p,m)
    assert r['nodata_value'] is None and r['nodata_value_nonfinite'] is True
    assert r['masked_pixels']==1
    json.dumps(r,allow_nan=False)


def test_pixel_limit(tmp_path,monkeypatch):
    import app.dem_audit as module
    p,m=raster(tmp_path);monkeypatch.setattr(module,'MAX_PIXELS',3)
    with pytest.raises(ValueError,match='pixels'):audit_dem(p,m)


def test_cli_and_corrupt_file_have_no_success_output(tmp_path):
    p,m=raster(tmp_path);manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps(m))
    cmd=[sys.executable,'-m','app.dem_audit',str(p),str(manifest)]
    r=subprocess.run(cmd,capture_output=True,text=True)
    assert r.returncode==0,r.stderr
    assert json.loads(r.stdout)['manifest_sha256']==sha256(manifest.read_bytes()).hexdigest()
    p.write_bytes(b'NOT_A_TIFF');rehash(p,m);manifest.write_text(json.dumps(m))
    r=subprocess.run(cmd,capture_output=True,text=True)
    assert r.returncode==2 and not r.stdout
