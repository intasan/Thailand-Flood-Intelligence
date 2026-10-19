"""Bounded manual job wrapper; does not download, schedule or publish data."""
from pathlib import Path
import re
from .observation_export import export_observations
from .rainfall_input import timestamp


def run_export_job(params,root):
    if not isinstance(params,dict) or params.get('accept_non_commercial') is not True:
        raise ValueError('Explicit HII non-commercial-use acknowledgement required')
    station=params.get('station');request=params.get('request_id')
    if not isinstance(station,str) or not re.fullmatch(r'[A-Z0-9]{2,20}',station):
        raise ValueError('Valid HII station code required')
    if not isinstance(request,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',request):
        raise ValueError('Explicit request_id of 1..64 letters/digits/underscore/hyphen required')
    start,end=params.get('start'),params.get('end')
    a,b=timestamp(start),timestamp(end)
    step=params.get('interval_seconds')
    duration=(b-a).total_seconds()
    if type(step) is not int or not 60<=step<=86400 or duration<=0 or duration>31*86400 or duration%step:
        raise ValueError('Require aligned positive <=31-day window and 60..86400 second grid')
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=True)
    target=root/request
    # Existing directories/symlinks are never reused or overwritten; a rerun needs a new ID.
    if target.exists() or target.is_symlink():
        raise FileExistsError('Export request already exists; choose a new request_id')
    result=export_observations('HII:'+station,start,end,step,['N'],target)
    return {**result,'request_id':request,'station_id':'HII:'+station,
        'window_start':a.isoformat(),'window_end':b.isoformat(),'interval_seconds':step,
        'relative_output_directory':request,'licence_scope':'HII non-commercial only',
        'timestamp_assumptions':'preserved_in_provenance_json'}
