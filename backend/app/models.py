"""Read-only serving of operator-reviewed solver outputs; no solver or invented hazard data."""
from datetime import datetime,timezone
import hashlib
import json
import math
import os
from pathlib import Path
import rasterio
import numpy as np
from .model_evidence import strict_json, verify_evidence, file_sha256
from rasterio.warp import transform

class ModelRejected(ValueError):pass

def timestamp(value):
    t=datetime.fromisoformat(value.replace('Z','+00:00'))
    if t.tzinfo is None:raise ModelRejected('Timezone required')
    return t

def validate_manifest(path):
    try:
        p=Path(path).resolve();m=strict_json(p)
        verify_evidence(p,m)
        for k in ('model_version','solver','vertical_datum','input_manifest_sha256','generated_at','valid_from','valid_to','resolution_m','uncertainty','input_provenance'):
            if not m.get(k):raise ModelRejected(f'Missing {k}')
        timestamp(m['generated_at'])
        if not isinstance(m.get('resolution_native'),list) or len(m['resolution_native'])!=2 or any(not math.isfinite(float(v)) or float(v)<=0 for v in m['resolution_native']):raise ModelRejected('Invalid native resolution')
        if not math.isfinite(float(m['resolution_m'])) or float(m['resolution_m'])<=0:raise ModelRejected('Invalid model resolution')
        if timestamp(m['valid_to'])<=timestamp(m['valid_from']):raise ModelRejected('Invalid validity interval')
        if m['depth_semantics']!='maximum_over_valid_interval':raise ModelRejected('Unsupported depth semantics')
        v=m['validation']
        if v['status']!='approved' or not v.get('reviewed_by') or not v.get('report_sha256'):raise ModelRejected('Missing independent approval')
        timestamp(v['reviewed_at'])
        if not v.get('calibration_event') or not v.get('validation_event') or v['calibration_event']==v['validation_event']:raise ModelRejected('Independent event required')
        metrics=v['metrics'];limits=v['acceptance_limits']
        for name in ('stage_rmse_m','extent_csi','volume_error_fraction'):
            actual=float(metrics[name]);limit=float(limits[name])
            if not math.isfinite(actual) or not math.isfinite(limit):raise ModelRejected('Non-finite metrics')
            if name=='extent_csi':
                if not 0<=limit<=actual<=1:raise ModelRejected('Extent validation failed')
            elif not 0<=actual<=limit:raise ModelRejected('Validation tolerance exceeded')
        for flag in ('datum_ties_verified','river_network_verified','boundary_conditions_verified','structures_reviewed','mesh_convergence_passed'):
            if v.get(flag) is not True:raise ModelRejected(f'Missing {flag}')
        if not m['input_provenance'] or any(not x.get('license_evidence') or not x.get('sha256') for x in m['input_provenance']):raise ModelRejected('Input provenance incomplete')
        for a in m['assets'].values():
            asset=(p.parent/a['path']).resolve()
            if not asset.is_relative_to(p.parent) or not asset.is_file():raise ModelRejected('Asset outside model directory or missing')
            if file_sha256(asset)!=a['sha256']:raise ModelRejected('Asset checksum mismatch')
            if a['unit'] not in ('m','h'):raise ModelRejected('Unsupported asset units')
        if m['assets']['max_depth']['unit']!='m':raise ModelRejected('Depth must be metres')
        if 'duration' in m['assets'] and m['assets']['duration']['unit']!='h':raise ModelRejected('Duration must be hours')
        validate_rasters(p,m)
        return m
    except (ValueError,KeyError,TypeError,OSError,AttributeError) as e:raise ModelRejected(str(e)) from e

def validate_rasters(path,manifest):
    for name,asset in manifest['assets'].items():
        if name not in ('max_depth','duration'):raise ModelRejected('Unknown hydraulic raster asset')
        with rasterio.open(path.parent/asset['path']) as ds:
            if ds.crs is None or ds.count!=1 or ds.nodata is None or ds.nodata==0:raise ModelRejected('Single-band georeferenced raster with explicit nonzero NoData required')
            if ds.tags().get('vertical_datum')!=manifest['vertical_datum']:raise ModelRejected('Raster vertical datum tag mismatch')
            if ds.crs.to_string()!=manifest['horizontal_crs']:raise ModelRejected('Raster horizontal CRS mismatch')
            if not np.allclose(ds.res,manifest['resolution_native'],rtol=1e-9,atol=0):raise ModelRejected('Raster native resolution mismatch')
            for _,window in ds.block_windows(1):
                values=ds.read(1,window=window,masked=True).compressed()*ds.scales[0]+ds.offsets[0]
                if np.any(~np.isfinite(values)) or np.any(values<0):raise ModelRejected('Raster contains invalid depth/duration values')
                if name=='duration' and np.any(values>(timestamp(manifest['valid_to'])-timestamp(manifest['valid_from'])).total_seconds()/3600):raise ModelRejected('Raster duration exceeds event interval')
    if 'duration' in manifest['assets']:
        with rasterio.open(path.parent/manifest['assets']['duration']['path']) as duration, rasterio.open(path.parent/manifest['assets']['max_depth']['path']) as depth:
            if (duration.crs,duration.transform,duration.width,duration.height)!=(depth.crs,depth.transform,depth.width,depth.height):raise ModelRejected('Depth/duration grids must align')

def sample_asset(path,lat,lon):
    with rasterio.open(path) as ds:
        if ds.crs is None or ds.count!=1:raise ModelRejected('Single-band georeferenced raster required')
        x,y=transform('EPSG:4326',ds.crs,[lon],[lat]);x,y=x[0],y[0]
        if not (ds.bounds.left<=x<ds.bounds.right and ds.bounds.bottom<y<=ds.bounds.top):return None
        v=next(ds.sample([(x,y)],masked=True))[0]
        if getattr(v,'mask',False):return None
        value=float(v)*ds.scales[0]+ds.offsets[0]
        if not math.isfinite(value) or value<0:raise ModelRejected('Invalid negative/non-finite model output')
        return value

def catalog():
    root=Path(os.getenv('MODEL_DIRECTORY','/app/models'))
    approved=[];rejected=0
    for path in sorted(root.glob('*/manifest.json')):
        try:approved.append((path,validate_manifest(path)))
        except ModelRejected:rejected+=1
    return approved,rejected

def model_point(lat,lon,at=None):
    t=timestamp(at) if at else datetime.now(timezone.utc)
    rows,rejected=catalog()
    # Most recently generated run has priority; unknown raster cells remain unknown.
    rows.sort(key=lambda row:timestamp(row[1]['generated_at']),reverse=True)
    for path,m in rows:
        if not timestamp(m['valid_from'])<=t<timestamp(m['valid_to']):continue
        depth=sample_asset(path.parent/m['assets']['max_depth']['path'],lat,lon)
        if depth is None:continue
        duration=sample_asset(path.parent/m['assets']['duration']['path'],lat,lon) if 'duration' in m['assets'] else None
        if duration is not None and duration>(timestamp(m['valid_to'])-timestamp(m['valid_from'])).total_seconds()/3600:raise ModelRejected('Duration exceeds event interval')
        return {'status':'available','flood_depth_m':depth,'duration_hours':duration,'risk':'not_classified',
            'metadata':{k:m[k] for k in ('model_version','solver','generated_at','valid_from','valid_to','vertical_datum','resolution_m','depth_semantics','uncertainty','validation','input_provenance')},
            'review_integrity_status':'trusted_signature_and_evidence_verified',
            'limitations':['ความลึกสูงสุดตลอดช่วงเหตุการณ์ ไม่ใช่ระดับน้ำ ณ เวลาที่ขอ','ยังไม่มีเกณฑ์จัดระดับความเสี่ยงต่อทรัพย์สิน']}
    return {'status':'unsupported','flood_depth_m':None,'duration_hours':None,'risk':'unknown','metadata':{'requested_at':t.isoformat(),'validation':{'status':'not_available'}},'rejected_packages':rejected}
