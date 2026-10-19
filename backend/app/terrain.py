"""Trusted local raster sampling, not a flood model. Not wired to public API."""
import math
import rasterio
from rasterio.warp import transform

def sample_elevation(path, lon, lat, metadata):
    if metadata.get('unit') != 'm' or not metadata.get('license_evidence') or not metadata.get('vertical_datum'):
        raise ValueError('Metre units, license and vertical datum required')
    with rasterio.open(path) as ds:
        if ds.crs is None: raise ValueError('Unknown raster CRS')
        xs,ys=transform('EPSG:4326',ds.crs,[lon],[lat]);x,y=xs[0],ys[0]
        if not (ds.bounds.left<=x<ds.bounds.right and ds.bounds.bottom<y<=ds.bounds.top): return None
        v=next(ds.sample([(x,y)],masked=True))[0]
        if getattr(v,'mask',False) or not math.isfinite(float(v)): return None
        return {'value_m':float(v),'vertical_datum':metadata['vertical_datum'],
            'horizontal_crs':ds.crs.to_string(),'pixel_size_native_units':list(ds.res),
            'terrain_type':metadata.get('terrain_type','unknown'),'provenance':metadata}
