"""Exact-time station water-level comparison; never hydraulic certification."""
import argparse
import csv
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
import math
from pathlib import Path
from .rainfall_input import timestamp, bounded_read, digest

MAX_PAIRS = 100000


def required_text(obj, keys):
    if not isinstance(obj,dict) or any(not isinstance(obj.get(k),str) or not obj[k].strip() for k in keys):
        raise ValueError('Missing source/model/datum provenance')


def load_series(raw, descriptor, stations, start, end, step):
    if not isinstance(raw,bytes) or len(raw)>10_000_000:
        raise ValueError('CSV must be bytes <=10 MB')
    digest(descriptor.get('raw_sha256'),'raw_sha256')
    if sha256(raw).hexdigest()!=descriptor['raw_sha256']:
        raise ValueError('Series CSV checksum mismatch')
    flags=descriptor.get('accepted_quality_flags')
    if not isinstance(flags,list) or not flags or any(not isinstance(v,str) or not v.strip() for v in flags) or len(set(flags))!=len(flags):
        raise ValueError('Explicit unique accepted_quality_flags required for both series')
    reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig'),newline=''),strict=True)
    if reader.fieldnames!=['station_id','observed_at','value_m','quality_flag']:
        raise ValueError('CSV columns must be station_id,observed_at,value_m,quality_flag')
    rows={}
    for line,row in enumerate(reader,2):
        if len(rows)>=MAX_PAIRS or None in row or any(v is None for v in row.values()):
            raise ValueError('Too many or malformed series rows')
        station=row['station_id']
        if station not in stations:
            raise ValueError('Unknown station_id')
        t=timestamp(row['observed_at']);offset=(t-start).total_seconds()
        if not start<=t<end or offset%step:
            raise ValueError('Timestamp outside study window or off grid')
        key=(station,int(offset/step))
        if key in rows:
            raise ValueError('Duplicate station/timestamp (including equivalent offsets)')
        value=None;status='accepted'
        try:
            value=float(row['value_m'])
            if not math.isfinite(value):raise ValueError()
        except (ValueError,OverflowError):
            value=None;status='quarantined_invalid_or_missing'
        if row['quality_flag'] not in flags:
            value=None;status='quarantined_quality_flag'
        rows[key]={'value_m':value,'status':status,'source_line':line,'quality_flag':row['quality_flag']}
    return rows


def metrics(errors):
    if len(errors)<2:
        return None
    if any(not math.isfinite(e) for e in errors):raise ValueError('Non-finite level error')
    n=len(errors);scale=max(abs(e) for e in errors)
    result={'mae_m':math.fsum(abs(e)/n for e in errors),
            'rmse_m':scale*math.sqrt(math.fsum((e/scale)**2/n for e in errors)) if scale else 0.0,
            'bias_m':math.fsum(e/n for e in errors),'max_abs_error_m':scale}
    if any(not math.isfinite(v) for v in result.values()):raise ValueError('Metric overflow')
    return result


def compare_levels(observed_raw,simulated_raw,manifest):
    if not isinstance(manifest,dict) or type(manifest.get('schema_version')) is not int or manifest['schema_version']!=1:
        raise ValueError('Level comparison schema_version=1 required')
    required_text(manifest,('event_id','datum_alignment_evidence'))
    calibration=manifest.get('calibration_event_ids')
    if not isinstance(calibration,list) or any(not isinstance(v,str) or not v.strip() for v in calibration) or len(set(calibration))!=len(calibration):
        raise ValueError('Explicit unique calibration_event_ids list required')
    if manifest['event_id'] in calibration:
        raise ValueError('Validation event must not appear in declared calibration events')
    observations=manifest.get('observations');simulations=manifest.get('simulations')
    common=('vertical_datum','unit','quantity')
    required_text(observations,(*common,'source_url','license','license_evidence','dataset_version','retrieved_at'))
    required_text(simulations,(*common,'model_name','model_version','run_id','generated_at','configuration_sha256'))
    timestamp(observations['retrieved_at']);timestamp(simulations['generated_at'])
    digest(simulations['configuration_sha256'],'configuration_sha256')
    if any(d['unit']!='m' or d['quantity']!='water_surface_elevation' for d in (observations,simulations)):
        raise ValueError('Both series require water_surface_elevation in m')
    if observations['vertical_datum']!=simulations['vertical_datum'] or observations['vertical_datum'].strip().lower() in ('unknown','unspecified','none'):
        raise ValueError('Same explicit vertical datum required; no offset guessed')
    stations=manifest.get('station_ids')
    if not isinstance(stations,list) or not stations or any(not isinstance(v,str) or not v.strip() for v in stations) or len(set(stations))!=len(stations):
        raise ValueError('Explicit nonempty unique station_ids required')
    start,end=timestamp(manifest.get('window_start')),timestamp(manifest.get('window_end'))
    step=manifest.get('interval_seconds');duration=(end-start).total_seconds()
    if type(step) is not int or not 60<=step<=86400 or duration<=0 or duration>31*86400 or duration%step:
        raise ValueError('Require aligned positive <=31-day study window and 60..86400 second intervals')
    bins=int(duration/step)
    if bins*len(stations)>MAX_PAIRS:raise ValueError('Maximum 100000 expected station/time pairs')
    obs=load_series(observed_raw,observations,set(stations),start,end,step)
    sim=load_series(simulated_raw,simulations,set(stations),start,end,step)
    reports=[];all_errors=[]
    for station in stations:
        paired=[];missing_obs=missing_sim=bad_obs=bad_sim=0
        for i in range(bins):
            a,b=obs.get((station,i)),sim.get((station,i))
            missing_obs+=a is None;missing_sim+=b is None
            bad_obs+=a is not None and a['status']!='accepted';bad_sim+=b is not None and b['status']!='accepted'
            if a is not None and b is not None and a['status']==b['status']=='accepted':
                error=b['value_m']-a['value_m']
                if not math.isfinite(error):raise ValueError('Level difference overflow')
                paired.append(error)
        all_errors.extend(paired)
        reports.append({'station_id':station,'expected_pairs':bins,'accepted_pairs':len(paired),
            'absent_observations':missing_obs,'absent_simulations':missing_sim,
            'quarantined_observations':bad_obs,'quarantined_simulations':bad_sim,
            'complete':len(paired)==bins,'paired_metrics':metrics(paired),
            'metrics_scope':'complete_window' if len(paired)==bins else 'accepted_pairs_only_incomplete_window'})
    complete=all(r['complete'] for r in reports)
    return {'status':'comparison_complete' if complete else 'comparison_incomplete',
        'comparison_version':'1.0.0','generated_at':datetime.now(timezone.utc).isoformat(),
        'provenance':manifest,'window_start':start.isoformat(),'window_end':end.isoformat(),
        'matching':'exact_UTC_station_timestamp_no_interpolation','error_sign':'simulated_minus_observed',
        'stations':reports,'pooled_accepted_pairs':len(all_errors),'pooled_paired_metrics':metrics(all_errors),
        'pooled_metrics_scope':'all_accepted_pairs_equal_weight_not_station_average',
        'scientific_validation':'not_certified','independence':'declared_event_ids_disjoint_not_independently_verified',
        'acceptance_decision':'not_assessed_no_thresholds_or_reviewer',
        'limitations':['Incomplete paired metrics can be biased by missing-data selection; no absent values are filled.',
            'Fewer than two accepted pairs yields null metrics; zero/negative datum elevations remain valid.',
            'Datum alignment evidence and calibration-event independence require independent review.',
            'Water-level errors do not validate flood extent, property depth or duration; no model approval is issued.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('observations',type=Path);parser.add_argument('simulations',type=Path);parser.add_argument('manifest',type=Path)
    args=parser.parse_args()
    try:
        raw=bounded_read(args.manifest,64000)
        report=compare_levels(bounded_read(args.observations,10_000_000),bounded_read(args.simulations,10_000_000),json.loads(raw))
        report['manifest_sha256']=sha256(raw).hexdigest()
    except (ValueError,OSError,csv.Error,OverflowError) as e:
        parser.exit(2,f'Level comparison rejected: {e}\n')
    print(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False))


if __name__=='__main__':main()
