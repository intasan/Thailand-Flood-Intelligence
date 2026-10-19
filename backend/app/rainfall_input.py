"""Prepare local catchment-mean rainfall intervals; never runoff or flood forecasts."""
import argparse
import csv
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import io
import json
import math
from pathlib import Path
from .river_network import audit_network

MAX_INTERVALS = 100000


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('Timestamp must be offset-bearing ISO8601')
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise ValueError('Timestamp must be offset-bearing ISO8601') from None
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError('Timestamp requires explicit timezone')
    return result.astimezone(timezone.utc)


def digest(value, label):
    if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError(f'{label} requires lowercase SHA256')


def prepare_rainfall(raw, manifest, network, network_sha256):
    if not isinstance(raw, bytes) or len(raw) > 10_000_000:
        raise ValueError('Rainfall CSV must be bytes, at most 10 MB')
    if not isinstance(manifest, dict) or type(manifest.get('schema_version')) is not int or manifest['schema_version'] != 1:
        raise ValueError('Rainfall schema_version=1 required')
    required = ('source_url', 'license', 'license_evidence', 'dataset_version', 'retrieved_at', 'spatial_averaging_evidence', 'approved_by')
    if any(not isinstance(manifest.get(k), str) or not manifest[k].strip() for k in required):
        raise ValueError('Missing rainfall source/rights/version/averaging/approval provenance')
    if manifest.get('approval_status') != 'approved':
        raise ValueError('Operator-approved rainfall input required')
    timestamp(manifest['retrieved_at'])
    if manifest.get('data_type') != 'historical_observation':
        raise ValueError('Only historical_observation rainfall is supported; forecasts are not observations')
    if manifest.get('unit') != 'mm' or manifest.get('quantity') != 'interval_accumulation' or manifest.get('spatial_support') != 'catchment_mean':
        raise ValueError('Require catchment_mean interval_accumulation in mm; point rain/intensity/cumulative counters unsupported')
    for field in ('raw_sha256', 'network_package_sha256'):
        digest(manifest.get(field), field)
    if sha256(raw).hexdigest() != manifest['raw_sha256']:
        raise ValueError('Rainfall CSV checksum mismatch')
    if manifest['network_package_sha256'] != network_sha256:
        raise ValueError('Network package checksum mismatch')
    report = audit_network(network)
    if report['catchment_geometry_check'] != 'non_overlapping_reach_coverage_checked':
        raise ValueError('Complete non-overlapping catchment geometries required')
    start, end = timestamp(manifest.get('window_start')), timestamp(manifest.get('window_end'))
    if end > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise ValueError('Historical observation window cannot end in the future')
    step = manifest.get('interval_seconds')
    if type(step) is not int or not 60 <= step <= 86400:
        raise ValueError('interval_seconds must be integer 60..86400')
    duration = (end-start).total_seconds()
    if duration <= 0 or duration > 31*86400 or duration % step:
        raise ValueError('Require positive <=31-day window aligned to interval_seconds')
    bins = int(duration/step)
    reaches = {r['id']: r for r in report['reaches']}
    if bins * len(reaches) > MAX_INTERVALS:
        raise ValueError('Maximum 100000 expected reach intervals; shorten window')
    flags = manifest.get('accepted_quality_flags')
    if not isinstance(flags, list) or not flags or any(not isinstance(f, str) or not f.strip() for f in flags) or len(set(flags)) != len(flags):
        raise ValueError('Explicit unique accepted_quality_flags required')
    try:
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''), strict=True)
    except UnicodeDecodeError:
        raise ValueError('Rainfall CSV requires UTF-8') from None
    fields = ['reach_id', 'start', 'end', 'rainfall_mm', 'quality_flag']
    if reader.fieldnames != fields:
        raise ValueError('CSV columns must be reach_id,start,end,rainfall_mm,quality_flag in this order')
    observed, records = {}, []
    by_reach = {rid: [] for rid in reaches}
    for line, row in enumerate(reader, 2):
        if len(records) >= MAX_INTERVALS:
            raise ValueError('Maximum 100000 input rows')
        if None in row or any(v is None for v in row.values()):
            raise ValueError(f'Line {line}: malformed CSV row')
        rid = row['reach_id']
        if rid not in reaches:
            raise ValueError(f'Line {line}: unknown reach_id')
        a, b = timestamp(row['start']), timestamp(row['end'])
        offset = (a-start).total_seconds()
        if a < start or b > end or (b-a).total_seconds() != step or offset % step:
            raise ValueError(f'Line {line}: interval outside window or off grid')
        key = (rid, int(offset/step))
        if key in observed:
            raise ValueError(f'Line {line}: duplicate or overlapping reach interval')
        status, value = 'accepted', None
        try:
            value = float(row['rainfall_mm'])
            if not math.isfinite(value) or value < 0:
                raise ValueError()
        except (ValueError, OverflowError):
            status, value = 'quarantined_invalid_or_missing', None
        if row['quality_flag'] not in flags:
            status, value = 'quarantined_quality_flag', None
        record = {'reach_id': rid, 'start': a.isoformat(), 'end': b.isoformat(), 'rainfall_mm': value,
                  'quality_flag': row['quality_flag'], 'status': status, 'source_line': line}
        observed[key] = record
        records.append(record); by_reach[rid].append(record)
    summaries = []
    for rid, reach in reaches.items():
        rows = by_reach[rid]
        valid = [r['rainfall_mm'] for r in rows if r['status'] == 'accepted']
        try:
            partial = math.fsum(valid) if valid else None
            complete = len(valid) == bins
            volume = partial/1000*reach['incremental_catchment_area_m2'] if complete else None
            if volume is not None and not math.isfinite(volume):
                raise OverflowError()
        except OverflowError:
            raise ValueError('Rainfall total or precipitation volume overflow') from None
        summaries.append({'reach_id': rid, 'expected_intervals': bins, 'received_intervals': len(rows),
            'accepted_intervals': len(valid), 'quarantined_intervals': len(rows)-len(valid),
            'absent_intervals': bins-len(rows), 'complete': complete,
            'known_interval_sum_mm': partial, 'total_rainfall_mm': partial if complete else None,
            'precipitation_volume_m3': volume, 'incremental_catchment_area_m2': reach['incremental_catchment_area_m2']})
    return {'status': 'prepared_complete' if all(r['complete'] for r in summaries) else 'prepared_incomplete',
        'generated_at': datetime.now(timezone.utc).isoformat(), 'preparation_version': '1.0.0',
        'window_start': start.isoformat(), 'window_end': end.isoformat(), 'interval_seconds': step,
        'unit': 'mm', 'quantity': 'interval_accumulation', 'spatial_support': 'catchment_mean', 'data_type': 'historical_observation',
        'provenance': dict(manifest), 'network_package_sha256': network_sha256,
        'network_audit_version': report['audit_version'], 'network_raw_source_checksum': 'not_checked',
        'summaries': summaries, 'records': sorted(records, key=lambda r:(r['reach_id'],r['start'])),
        'validation': {'status': 'structural_checks_only', 'hydraulic_validation': 'not_performed'},
        'limitations': ['No interpolation; absent or quarantined intervals never become zero rainfall.',
            'Precipitation volume assumes supplied catchment-mean rainfall; not runoff or river discharge.',
            'Operator assertions and spatial averaging require independent source and scientific review.',
            'No routing, tide, barriers, water levels, inundation or property risk is computed.']}


def bounded_read(path, limit):
    with path.open('rb') as f:
        raw = f.read(limit+1)
    if len(raw) > limit:
        raise ValueError(f'File exceeds {limit} bytes')
    return raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', type=Path)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--network', type=Path, required=True)
    parser.add_argument('--network-raw-source', type=Path, required=True)
    args = parser.parse_args()
    try:
        raw = bounded_read(args.csv, 10_000_000)
        manifest_raw = bounded_read(args.manifest, 64000)
        manifest = json.loads(manifest_raw)
        network_raw = bounded_read(args.network, 20_000_000)
        network = json.loads(network_raw)
        report = prepare_rainfall(raw, manifest, network, sha256(network_raw).hexdigest())
        source_hash = sha256()
        with args.network_raw_source.open('rb') as f:
            for chunk in iter(lambda:f.read(1024*1024), b''):
                source_hash.update(chunk)
        if source_hash.hexdigest() != network['provenance']['raw_sha256']:
            raise ValueError('Network original source checksum mismatch')
        report['network_raw_source_checksum'] = 'matched'
        report['manifest_sha256'] = sha256(manifest_raw).hexdigest()
    except (ValueError, OSError, csv.Error) as e:
        parser.exit(2, f'Rainfall rejected: {e}\n')
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
