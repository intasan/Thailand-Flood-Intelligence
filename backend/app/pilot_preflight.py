"""Read-only pilot input preflight; never model approval or hydraulic validation."""
import argparse
import csv
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.windows import Window, from_bounds
from pyproj import Transformer
from pyproj.exceptions import ProjError
from shapely.errors import GEOSException
from shapely import segmentize, get_num_coordinates
from shapely.geometry import shape, box, mapping
from shapely.ops import transform
from .dem_audit import audit_dem
from .rainfall_input import prepare_rainfall, bounded_read

MAX_COVERAGE_PIXELS = 100_000_000
MAX_TRANSFORM_POSITIONS = 1_000_000


def file_hash(path):
    h=sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()


def coverage(raster, network):
    """Conservative touched-pixel test, not a surveyed area-coverage calculation."""
    results=[]; evaluated=0; transformed_positions=0
    with rasterio.open(raster) as ds:
        project=Transformer.from_crs('EPSG:4326',ds.crs,always_xy=True).transform
        grid=box(*ds.bounds)
        for reach in network['reaches']:
            geometry=shape(reach['incremental_catchment_geometry'])
            # Bound densification before allocating new coordinates.
            components=[geometry] if geometry.geom_type=='Polygon' else list(geometry.geoms)
            estimate=0
            for polygon in components:
                for ring in [polygon.exterior,*polygon.interiors]:
                    for a,b in zip(ring.coords,list(ring.coords)[1:]):
                        estimate+=max(1,math.ceil(math.hypot(b[0]-a[0],b[1]-a[1])/.001))
            if transformed_positions+estimate>MAX_TRANSFORM_POSITIONS:
                raise ValueError('Catchment densification limit exceeded')
            dense=segmentize(geometry,.001)
            transformed_positions+=int(get_num_coordinates(dense))
            if transformed_positions>MAX_TRANSFORM_POSITIONS:
                raise ValueError('Catchment transformation position limit exceeded')
            projected=transform(project,dense)
            if not projected.is_valid or projected.is_empty or not all(math.isfinite(v) for v in projected.bounds):
                raise ValueError('Catchment transformation failed')
            inside=grid.covers(projected)
            clipped=projected.intersection(grid)
            selected=valid=invalid=0
            if not clipped.is_empty and clipped.area>0:
                window=from_bounds(*clipped.bounds,transform=ds.transform)
                x0=max(0,int(math.floor(window.col_off)));y0=max(0,int(math.floor(window.row_off)))
                x1=min(ds.width,int(math.ceil(window.col_off+window.width)))
                y1=min(ds.height,int(math.ceil(window.row_off+window.height)))
                evaluated+=(x1-x0)*(y1-y0)
                if evaluated>MAX_COVERAGE_PIXELS:
                    raise ValueError('Coverage pixel evaluation limit exceeded; reduce study extent')
                geom=mapping(projected)
                for y in range(y0,y1,512):
                    for x in range(x0,x1,512):
                        w=Window(x,y,min(512,x1-x),min(512,y1-y))
                        touched=geometry_mask([geom],out_shape=(int(w.height),int(w.width)),transform=ds.window_transform(w),all_touched=True,invert=True)
                        data=ds.read(1,window=w,masked=True)
                        usable=~np.ma.getmaskarray(data)&np.isfinite(data.data)
                        selected+=int(touched.sum());valid+=int((touched&usable).sum())
                        invalid+=int((touched&~usable).sum())
            complete=inside and selected>0 and invalid==0
            results.append({'reach_id':reach['id'],'within_raster_bounds':inside,
                'touched_pixels':selected,'valid_touched_pixels':valid,'invalid_touched_pixels':invalid,
                'coverage_status':'complete_touched_pixels' if complete else 'incomplete_or_outside',
                'invalid_touched_fraction':invalid/selected if selected else None})
    return {'method':'WGS84 edges densified <=0.001 degrees then transformed; all_touched pixels',
        'boundary_accuracy':'approximate_not_surveyed','transformed_positions':transformed_positions,'pixel_evaluations':evaluated,'catchments':results,
        'complete':all(r['coverage_status']=='complete_touched_pixels' for r in results)}


def audit_pilot(bundle_path):
    bundle_path=Path(bundle_path).resolve()
    raw=bounded_read(bundle_path,64000);bundle=json.loads(raw)
    if not isinstance(bundle,dict) or type(bundle.get('schema_version')) is not int or bundle['schema_version']!=1:
        raise ValueError('Pilot schema_version=1 required')
    pilot=bundle.get('pilot_id')
    if not isinstance(pilot,str) or not pilot.strip() or len(pilot)>100:
        raise ValueError('pilot_id must be nonempty and <=100 characters')
    names=('network','network_raw_source','rainfall_csv','rainfall_manifest','dem','dem_manifest')
    files=bundle.get('files')
    if not isinstance(files,dict) or set(files)!=set(names):
        raise ValueError('Exactly six named input files required')
    root=bundle_path.parent;paths={}
    for name,value in files.items():
        if not isinstance(value,str) or not value or Path(value).is_absolute():
            raise ValueError('Input paths must be relative to the pilot bundle')
        path=(root/value).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('Input paths must remain inside bundle directory and exist')
        paths[name]=path
    network_raw=bounded_read(paths['network'],20_000_000);network=json.loads(network_raw)
    rain_manifest_raw=bounded_read(paths['rainfall_manifest'],64000)
    rainfall=prepare_rainfall(bounded_read(paths['rainfall_csv'],10_000_000),json.loads(rain_manifest_raw),network,sha256(network_raw).hexdigest())
    source_hash=file_hash(paths['network_raw_source'])
    if source_hash!=network['provenance']['raw_sha256']:
        raise ValueError('Network original source checksum mismatch')
    rainfall['network_raw_source_checksum']='matched'
    dem_manifest_raw=bounded_read(paths['dem_manifest'],64000)
    dem=audit_dem(paths['dem'],json.loads(dem_manifest_raw))
    terrain_coverage=coverage(paths['dem'],network)
    blockers=[]
    if rainfall['status']!='prepared_complete':blockers.append('rainfall_incomplete')
    if not terrain_coverage['complete']:blockers.append('dem_catchment_coverage_incomplete')
    if dem['terrain_type']!='DTM':blockers.append('bare_earth_terrain_not_established')
    # These cannot be cleared by metadata assertions or software integrity alone.
    scientific=['surveyed_datum_alignment_not_verified','boundary_hydrographs_not_registered',
        'channel_geometry_and_barriers_not_verified','rainfall_runoff_model_not_calibrated',
        'hydraulic_solver_and_independent_validation_not_registered']
    return {'pilot_id':pilot,'preflight_version':'1.0.0','generated_at':datetime.now(timezone.utc).isoformat(),
        'status':'input_checks_passed' if not blockers else 'input_gaps_detected',
        'hydraulic_ready':False,'hydraulic_validation':'not_performed',
        'input_blockers':blockers,'scientific_blockers':scientific,
        'hashes':{'bundle':sha256(raw).hexdigest(),'network':sha256(network_raw).hexdigest(),
            'network_raw_source':source_hash,'rainfall_csv':rainfall['provenance']['raw_sha256'],
            'rainfall_manifest':sha256(rain_manifest_raw).hexdigest(),'dem':dem['raw_sha256'],
            'dem_manifest':sha256(dem_manifest_raw).hexdigest()},
        'network':{'audit_version':rainfall['network_audit_version'],'raw_source_checksum':'matched'},
        'rainfall':{k:v for k,v in rainfall.items() if k!='records'},'dem':dem,'dem_catchment_coverage':terrain_coverage,
        'limitations':['This report is not registered as approved pilot/model coverage or served to public APIs.',
            'DEM coverage uses approximate transformed geometry and touched pixels, not surveyed area or hydrologic connectivity.',
            'No flood depth, duration, river discharge, water accessibility or property risk is inferred.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('bundle',type=Path);args=parser.parse_args()
    try:report=audit_pilot(args.bundle)
    except (ValueError,OSError,csv.Error,rasterio.errors.RasterioError,OverflowError,ProjError,GEOSException) as e:
        parser.exit(2,f'Pilot rejected: {e}\n')
    print(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False))


if __name__=='__main__':main()
