"""Read-only serving of operator-reviewed solver outputs; no solver or invented hazard data."""
from datetime import datetime,timezone
import hashlib
import json
import math
import os
from pathlib import Path
import rasterio
from rasterio.warp import transform

class ModelRejected(ValueError):pass

def timestamp(value):
    t=datetime.fromisoformat(value.replace('Z','+00:00'))
    if t.tzinfo is None:raise ModelRejected('Timezone required')
    return t

def validate_manifest(path):
    try:
        p=Path(path).resolve();m=json.loads(p.read_text())
        for k in ('model_version','solver','vertical_datum','input_manifest_sha256','generated_at','valid_from','valid_to','resolution_m','uncertainty','input_provenance'):
            if not m.get(k):raise ModelRejected(f'Missing {k}')
        timestamp(m['generated_at'])
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
            if hashlib.sha256(asset.read_bytes()).hexdigest()!=a['sha256']:raise ModelRejected('Asset checksum mismatch')
            if a['unit'] not in ('m','h'):raise ModelRejected('Unsupported asset units')
        if m['assets']['max_depth']['unit']!='m':raise ModelRejected('Depth must be metres')
        if 'duration' in m['assets'] and m['assets']['duration']['unit']!='h':raise ModelRejected('Duration must be hours')
        return m
    except (ValueError,KeyError,TypeError,OSError) as e:raise ModelRejected(str(e)) from e

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
            'limitations':['ความลึกสูงสุดตลอดช่วงเหตุการณ์ ไม่ใช่ระดับน้ำ ณ เวลาที่ขอ','ยังไม่มีเกณฑ์จัดระดับความเสี่ยงต่อทรัพย์สิน']}
    return {'status':'unsupported','flood_depth_m':None,'duration_hours':None,'risk':'unknown','metadata':{'requested_at':t.isoformat(),'validation':{'status':'not_available'}},'rejected_packages':rejected}
