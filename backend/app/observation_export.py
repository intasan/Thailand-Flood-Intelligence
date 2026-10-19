"""Export approved historical database observations for exact-time model comparison."""
import argparse
import csv
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
import math
from pathlib import Path
from .rainfall_input import timestamp, digest
from .repository import connect


def fetch_snapshot(station_id,start,end):
    # Source approval, metadata and rows come from the same read-only snapshot.
    with connect() as c:
        c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
        station=c.execute('''SELECT s.id,s.vertical_datum,s.metadata,src.id AS source_id,src.title AS source,
            src.url AS source_url,src.license_evidence FROM stations s JOIN sources src ON src.id=s.source_id
            WHERE s.id=%s AND src.approval_status='approved' AND length(trim(src.license_evidence))>0''',(station_id,)).fetchone()
        if not station:raise ValueError('Approved licensed station not found')
        rows=c.execute('''SELECT observed_at,value,unit,raw_sha256,metadata FROM observations
            WHERE station_id=%s AND observed_at>=%s AND observed_at<%s ORDER BY observed_at LIMIT 10001''',(station_id,start,end)).fetchall()
        if len(rows)>10000:raise ValueError('Maximum 10000 observations; shorten window')
    return station,rows


def prepare_export(station,rows,start,end,interval_seconds,accepted_flags):
    start,end=timestamp(start),timestamp(end)
    seconds=(end-start).total_seconds()
    if type(interval_seconds) is not int or not 60<=interval_seconds<=86400 or seconds<=0 or seconds>31*86400 or seconds%interval_seconds:
        raise ValueError('Require aligned positive <=31-day window and 60..86400 second grid')
    if not isinstance(accepted_flags,list) or not accepted_flags or any(not isinstance(f,str) or not f.strip() for f in accepted_flags) or len(set(accepted_flags))!=len(accepted_flags):
        raise ValueError('Explicit unique accepted quality flags required')
    for key in ('id','vertical_datum','source_id','source_url','license_evidence'):
        if not isinstance(station.get(key),str) or not station[key].strip():raise ValueError('Missing approved source/station/datum metadata')
    from .hii_archive import SOURCE, DATUM
    if station['source_id']!=SOURCE or station['vertical_datum']!=DATUM:
        raise ValueError('Only the registered HII historical MSL adapter is supported')
    if accepted_flags!=['N']:
        raise ValueError('HII export accepts only the documented N quality flag')
    if not rows or len(rows)>10000:raise ValueError('Require 1..10000 actual observation rows')
    stream=io.StringIO(newline='');writer=csv.writer(stream,lineterminator='\n')
    writer.writerow(['station_id','observed_at','value_m','quality_flag'])
    provenance=[];seen=set();accepted=0
    for row in rows:
        t=timestamp(row['observed_at'].isoformat() if isinstance(row['observed_at'],datetime) else row['observed_at'])
        if not start<=t<end or (t-start).total_seconds()%interval_seconds or t in seen:
            raise ValueError('Duplicate/out-of-window/off-grid observation')
        seen.add(t)
        if row.get('unit')!='m' or isinstance(row.get('value'),bool) or not isinstance(row.get('value'),(int,float)) or not math.isfinite(row['value']):
            raise ValueError('Finite metre observation required')
        digest(row.get('raw_sha256'),'observation raw_sha256')
        metadata=row.get('metadata')
        if not isinstance(metadata,dict) or metadata.get('data_type')!='historical_station_observation':
            raise ValueError('Explicit historical station observation metadata required')
        for key in ('source_quality_flag','timestamp_status','source_url'):
            if not isinstance(metadata.get(key),str) or not metadata[key].strip():raise ValueError('Missing observation provenance or quality/time status')
        if metadata['timestamp_status'].startswith('assumed') and not metadata.get('source_timezone'):
            raise ValueError('Assumed timestamp requires source timezone')
        flag=metadata['source_quality_flag'];ok=flag in accepted_flags;accepted+=ok
        writer.writerow([station['id'],t.isoformat(),repr(float(row['value'])) if ok else '',flag])
        provenance.append({**metadata,'observed_at':t.isoformat(),'raw_sha256':row['raw_sha256']})
    raw=stream.getvalue().encode('utf-8')
    now=datetime.now(timezone.utc).isoformat()
    hashes=sorted({r['raw_sha256'] for r in provenance})
    descriptor={'source_url':station['source_url'],'license':station['license_evidence'],
        'license_evidence':station['license_evidence'],'dataset_version':'raw-files-sha256:'+','.join(hashes),
        'retrieved_at':now,'retrieved_at_semantics':'database_snapshot_export_time_not_original_source_download',
        'vertical_datum':station['vertical_datum'],'unit':'m','quantity':'water_surface_elevation',
        'raw_sha256':sha256(raw).hexdigest(),'accepted_quality_flags':accepted_flags,
        'timestamp_assumptions_preserved_in':'provenance.json','datum_alignment':'not_verified'}
    evidence={'export_version':'1.0.0','generated_at':now,'station':station,
        'window_start':start.isoformat(),'window_end':end.isoformat(),'interval_seconds':interval_seconds,
        'expected_intervals':int(seconds/interval_seconds),'exported_rows':len(rows),'accepted_rows':accepted,
        'absent_intervals':int(seconds/interval_seconds)-len(rows),'flag_rejected_rows':len(rows)-accepted,
        'observations_sha256':descriptor['raw_sha256'],'original_raw_sha256':hashes,'records':provenance,
        'limitations':['This exports historical measured observations only; no simulated series is generated.',
            'Timestamp timezone assumptions are inherited from import and are not independently resolved.',
            'Published station datum is not reconciled to model/DEM datum; independent survey evidence is still required.',
            'Licence evidence is retained as stored, not upgraded or re-licensed; source release version may be unavailable.']}
    return raw,descriptor,evidence


def export_observations(station_id,start,end,interval_seconds,accepted_flags,destination):
    a,b=timestamp(start),timestamp(end)
    if b<=a or (b-a).total_seconds()>31*86400:raise ValueError('Require positive <=31-day window')
    station,rows=fetch_snapshot(station_id,a,b)
    raw,descriptor,evidence=prepare_export(station,rows,start,end,interval_seconds,accepted_flags)
    destination=Path(destination)
    destination.mkdir(parents=False,exist_ok=False)
    created=[]
    try:
        contents={'observations.csv':raw,
            'observations-descriptor.json':(json.dumps(descriptor,ensure_ascii=False,indent=2)+'\n').encode(),
            'provenance.json':(json.dumps(evidence,ensure_ascii=False,indent=2,default=lambda v:v.isoformat() if isinstance(v,datetime) else str(v))+'\n').encode()}
        for name,data in contents.items():
            p=destination/name
            with p.open('xb') as f:
                created.append(p)
                f.write(data)
    except Exception:
        for p in created:p.unlink()
        destination.rmdir()
        raise
    return {'status':'historical_observations_exported','rows':len(rows),'accepted_rows':evidence['accepted_rows'],
        'absent_intervals':evidence['absent_intervals'],'observations_sha256':descriptor['raw_sha256'],
        'files':list(contents),'simulation_generated':False,'datum_alignment':'not_verified'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--station',required=True);parser.add_argument('--start',required=True);parser.add_argument('--end',required=True)
    parser.add_argument('--interval-seconds',type=int,required=True)
    parser.add_argument('--accepted-flag',action='append',required=True)
    parser.add_argument('--destination',type=Path,required=True)
    args=parser.parse_args()
    try:report=export_observations(args.station,args.start,args.end,args.interval_seconds,args.accepted_flag,args.destination)
    except Exception as e:
        # Never print connection strings or server error details.
        parser.exit(2,f'Observation export rejected: {str(e) if isinstance(e,(ValueError,FileExistsError)) else type(e).__name__}\n')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
