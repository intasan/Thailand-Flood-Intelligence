"""Local GeoTIFF elevation integrity audit; no hydraulic validation or approval."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from .json_input import strict_json_loads
import math
from pathlib import Path
import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.windows import Window
from pyproj import CRS as PyCRS

MAX_PIXELS = 100_000_000
MAX_BYTES = 2_000_000_000


def audit_dem(path, manifest):
    path = Path(path)
    if not path.is_file() or path.suffix.lower() not in ('.tif', '.tiff'):
        raise ValueError('Local .tif/.tiff file required')
    if path.stat().st_size > MAX_BYTES:
        raise ValueError('GeoTIFF exceeds 2 GB')
    if not isinstance(manifest, dict) or type(manifest.get('schema_version')) is not int or manifest['schema_version'] != 1:
        raise ValueError('DEM schema_version=1 required')
    required = ('source_url','license','license_evidence','dataset_version','retrieved_at','vertical_datum','vertical_datum_evidence','horizontal_crs')
    if any(not isinstance(manifest.get(k), str) or not manifest[k].strip() for k in required):
        raise ValueError('Missing source, rights, CRS or datum evidence')
    if manifest.get('unit') != 'm' or manifest.get('terrain_type') not in ('DTM','DSM'):
        raise ValueError('Metre elevation unit and explicit DTM/DSM type required')
    if manifest['vertical_datum'].strip().lower() in ('unknown','unspecified','none'):
        raise ValueError('Named vertical datum required')
    try:
        retrieved = datetime.fromisoformat(manifest['retrieved_at'].replace('Z','+00:00'))
        if retrieved.tzinfo is None or retrieved.utcoffset() is None:
            raise ValueError()
    except ValueError:
        raise ValueError('retrieved_at requires offset-bearing ISO8601') from None
    expected = manifest.get('raw_sha256')
    if not isinstance(expected,str) or len(expected)!=64 or any(c not in '0123456789abcdef' for c in expected):
        raise ValueError('raw_sha256 requires lowercase SHA256')
    digest = sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):
            digest.update(chunk)
    if digest.hexdigest()!=expected:
        raise ValueError('GeoTIFF checksum mismatch')
    with rasterio.open(path) as ds:
        if any(Path(f).resolve()!=path.resolve() for f in ds.files):
            raise ValueError('External sidecar/mask files are unsupported; make a self-contained GeoTIFF')
        if ds.driver!='GTiff' or ds.count!=1 or ds.crs is None:
            raise ValueError('Single-band GeoTIFF with known CRS required')
        if ds.width*ds.height>MAX_PIXELS:
            raise ValueError('Maximum 100 million raster pixels')
        if np.dtype(ds.dtypes[0]).kind not in ('i','u','f'):
            raise ValueError('Real numeric elevation band required')
        if ds.crs!=CRS.from_user_input(manifest['horizontal_crs']):
            raise ValueError('Horizontal CRS differs from manifest')
        t=ds.transform
        if not all(math.isfinite(v) for v in list(t)[:6]) or t.b!=0 or t.d!=0 or t.a<=0 or t.e>=0:
            raise ValueError('Finite north-up affine grid required; no automatic warp')
        if ds.scales!=(1.0,) or ds.offsets!=(0.0,):
            raise ValueError('Scaled/offset bands must be normalized explicitly before audit')
        if ds.units[0] is not None and ds.units[0].lower() not in ('m','metre','meter','metres','meters'):
            raise ValueError('Raster elevation unit contradicts metre manifest')
        tagged_datum=ds.tags().get('VERTICAL_DATUM') or ds.tags(1).get('VERTICAL_DATUM')
        if tagged_datum and tagged_datum!=manifest['vertical_datum']:
            raise ValueError('Raster vertical datum tag contradicts manifest')
        declared=manifest.get('pixel_size_native_units')
        if not isinstance(declared,list) or len(declared)!=2:
            raise ValueError('Declare two pixel_size_native_units values')
        for a,b in zip(declared,ds.res):
            if isinstance(a,bool) or not isinstance(a,(int,float)) or not math.isfinite(a) or a<=0 or not math.isclose(a,b,rel_tol=1e-6,abs_tol=1e-9):
                raise ValueError('Declared pixel size differs from raster')
        crs=PyCRS.from_wkt(ds.crs.to_wkt())
        axes=crs.axis_info
        if len(axes)<2:
            raise ValueError('Horizontal axis units unavailable')
        units=[axis.unit_name for axis in axes[:2]]
        metre_grid=crs.is_projected and all(math.isclose(axis.unit_conversion_factor,1) and axis.unit_name.lower() in ('metre','meter') for axis in axes[:2])
        valid=masked=nonfinite=0
        minimum=maximum=None
        for y in range(0,ds.height,512):
            for x in range(0,ds.width,512):
                data=ds.read(1,window=Window(x,y,min(512,ds.width-x),min(512,ds.height-y)),masked=True)
                mask=np.ma.getmaskarray(data)
                finite=np.isfinite(data.data)
                masked+=int(mask.sum()); nonfinite+=int((~mask & ~finite).sum())
                values=data.data[~mask & finite]
                valid+=values.size
                if values.size:
                    low,high=float(values.min()),float(values.max())
                    minimum=low if minimum is None else min(minimum,low)
                    maximum=high if maximum is None else max(maximum,high)
        total=ds.width*ds.height
        nodata=ds.nodata
        return {'status':'integrity_checks_passed','audit_version':'1.0.0',
            'generated_at':datetime.now(timezone.utc).isoformat(),'raw_sha256':digest.hexdigest(),
            'provenance':dict(manifest),'horizontal_crs':ds.crs.to_string(),
            'vertical_datum':manifest['vertical_datum'],'datum_alignment':'not_verified',
            'terrain_type':manifest['terrain_type'],'unit':'m','width':ds.width,'height':ds.height,
            'bounds_native_units':list(ds.bounds),'pixel_size_native_units':list(ds.res),
            'horizontal_axis_units':units,'pixel_size_m':list(ds.res) if metre_grid else None,
            'nodata_value':nodata if nodata is not None and math.isfinite(nodata) else None,
            'nodata_value_nonfinite':nodata is not None and not math.isfinite(nodata),
            'coverage_scope':'entire_raster_grid_only','total_pixels':total,'valid_pixels':int(valid),
            'masked_pixels':masked,'unmasked_nonfinite_pixels':nonfinite,
            'invalid_fraction':(masked+nonfinite)/total,'min_elevation_m':minimum,'max_elevation_m':maximum,
            'coverage_status':'no_usable_pixels' if valid==0 else 'complete_grid' if valid==total else 'partial_grid',
            'accuracy_status':'not_independently_validated','hydraulic_validation':'not_performed',
            'limitations':['Coverage is for this raster grid, not completeness of any pilot basin or property.',
                'Native geographic pixel sizes are degrees; no constant metre resolution is inferred.',
                'DSM may include buildings/vegetation; DTM labels and datum evidence require human review.',
                'No vertical transformation, survey validation, barrier/drainage inference or inundation is computed.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raster',type=Path);parser.add_argument('manifest',type=Path)
    args=parser.parse_args()
    try:
        with args.manifest.open('rb') as f:
            raw=f.read(64001)
        if len(raw)>64000:
            raise ValueError('Manifest exceeds 64000 bytes')
        report=audit_dem(args.raster,strict_json_loads(raw))
        report['manifest_sha256']=sha256(raw).hexdigest()
    except (ValueError,OSError,rasterio.errors.RasterioError,OverflowError) as e:
        parser.exit(2,f'DEM rejected: {e}\n')
    print(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False))


if __name__=='__main__':
    main()
