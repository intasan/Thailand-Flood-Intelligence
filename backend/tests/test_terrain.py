import numpy as np
import rasterio
from rasterio.transform import from_origin
from app.terrain import sample_elevation

def test_local_raster_nodata_and_bounds(tmp_path):
    path=tmp_path/'test-only.tif'
    with rasterio.open(path,'w',driver='GTiff',width=2,height=2,count=1,dtype='float32',crs='EPSG:4326',transform=from_origin(100,14,0.01,0.01),nodata=-9999) as ds:
        ds.write(np.array([[5,-9999],[6,7]],dtype='float32'),1)
    meta={'license_evidence':'synthetic unit test only','vertical_datum':'TEST','unit':'m'}
    assert sample_elevation(path,100.005,13.995,meta)['value_m']==5
    assert sample_elevation(path,100.015,13.995,meta) is None
    assert sample_elevation(path,101,15,meta) is None
