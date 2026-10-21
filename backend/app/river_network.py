"""Offline directed river-network audit, never a hydraulic or flood model."""
import argparse
from collections import deque
from datetime import datetime, timezone
from hashlib import sha256
import json
from .json_input import strict_json_loads
import math
from pathlib import Path
from pyproj import Geod

GEOD = Geod(ellps='WGS84')
MAX_BYTES = 20_000_000


def number(value, label, minimum=0):
    try:
        valid = not isinstance(value, bool) and isinstance(value, (float, int)) and math.isfinite(value) and value >= minimum
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(f'{label} must be finite and >= {minimum}')
    return value


def audit_network(package, tolerance_m=30):
    """Coordinates run upstream to downstream; never reverse them automatically."""
    number(tolerance_m, 'tolerance_m')
    if tolerance_m > 1000:
        raise ValueError('tolerance_m must be <= 1000')
    if not isinstance(package, dict) or type(package.get('schema_version')) is not int or package.get('schema_version') != 1 or package.get('crs') != 'EPSG:4326':
        raise ValueError('Require schema_version=1 and crs=EPSG:4326')
    provenance = package.get('provenance')
    required = ('source_url', 'license', 'license_evidence', 'retrieved_at', 'dataset_version', 'raw_sha256', 'direction_evidence')
    if not isinstance(provenance, dict) or any(not isinstance(provenance.get(k), str) or not provenance[k].strip() for k in required):
        raise ValueError('Missing source/license/version/direction provenance')
    digest = provenance['raw_sha256']
    if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
        raise ValueError('raw_sha256 must be a lowercase SHA256 digest')
    try:
        fetched = datetime.fromisoformat(provenance['retrieved_at'].replace('Z', '+00:00'))
        if fetched.tzinfo is None or fetched.utcoffset() is None:
            raise ValueError()
    except ValueError:
        raise ValueError('retrieved_at requires timezone-aware ISO8601') from None
    rows = package.get('reaches')
    if not isinstance(rows, list) or not 1 <= len(rows) <= 10000:
        raise ValueError('Require 1..10000 reaches')
    reaches, lengths = {}, {}
    positions = 0
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Each reach must be an object')
        rid = row.get('id')
        if not isinstance(rid, str) or not rid.strip() or len(rid) > 100 or rid in reaches:
            raise ValueError('Reach IDs must be unique nonempty strings <= 100 characters')
        if 'downstream_id' not in row:
            raise ValueError(f'{rid}: explicit downstream_id or null outlet required')
        downstream = row.get('downstream_id')
        if downstream is not None and (not isinstance(downstream, str) or not downstream.strip()):
            raise ValueError(f'Invalid downstream_id for {rid}')
        geometry = row.get('geometry')
        coords = geometry.get('coordinates') if isinstance(geometry, dict) and geometry.get('type') == 'LineString' else None
        if not isinstance(coords, list) or len(coords) < 2:
            raise ValueError(f'{rid}: require directed 2D LineString')
        positions += len(coords)
        if positions > 200000:
            raise ValueError('Maximum 200000 coordinate positions')
        for p in coords:
            if not isinstance(p, list) or len(p) != 2:
                raise ValueError(f'{rid}: require longitude, latitude positions')
            number(p[0], 'longitude', -180); number(p[1], 'latitude', -90)
            if p[0] > 180 or p[1] > 90:
                raise ValueError(f'{rid}: coordinate out of bounds')
        length = GEOD.line_length([p[0] for p in coords], [p[1] for p in coords])
        if not math.isfinite(length) or length <= 0:
            raise ValueError(f'{rid}: invalid or zero-length reach')
        area = row.get('incremental_catchment_area_m2')
        if area is not None:
            number(area, f'{rid}: incremental_catchment_area_m2')
        reaches[rid], lengths[rid] = row, length
    indegree = dict.fromkeys(reaches, 0)
    upstream = {rid: [] for rid in reaches}
    for rid, row in reaches.items():
        target = row.get('downstream_id')
        if target is None:
            continue
        if target not in reaches or target == rid:
            raise ValueError(f'{rid}: missing or self downstream reference')
        a = row['geometry']['coordinates'][-1]
        b = reaches[target]['geometry']['coordinates'][0]
        distance = GEOD.inv(*a, *b)[2]
        if distance > tolerance_m:
            raise ValueError(f'{rid} -> {target}: endpoint gap {distance:.3f} m exceeds tolerance')
        indegree[target] += 1
        upstream[target].append(rid)
    queue = deque(sorted(rid for rid, degree in indegree.items() if degree == 0))
    order = []
    while queue:
        rid = queue.popleft(); order.append(rid)
        target = reaches[rid].get('downstream_id')
        if target is not None:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if len(order) != len(reaches):
        raise ValueError('Directed cycle detected; tidal/reversing networks require another representation')
    from .catchments import catchment_areas
    geometry_areas = catchment_areas(reaches, provenance)
    areas = {}
    for rid in order:
        local = geometry_areas[rid] if geometry_areas is not None else reaches[rid].get('incremental_catchment_area_m2')
        parents = upstream[rid]
        try:
            areas[rid] = None if local is None or any(areas[p] is None for p in parents) else math.fsum([local, *(areas[p] for p in parents)])
        except OverflowError:
            raise ValueError('Accumulated area overflow') from None
    return {'status': 'structural_checks_passed', 'hydraulic_validation': 'not_performed',
        'generated_at': datetime.now(timezone.utc).isoformat(), 'audit_version': '1.1.0',
        'provenance': dict(provenance), 'raw_source_checksum': 'not_checked', 'endpoint_tolerance_m': tolerance_m,
        'catchment_geometry_check': 'non_overlapping_reach_coverage_checked' if geometry_areas is not None else 'not_supplied',
        'area_method': 'WGS84_ellipsoidal_from_geometry' if geometry_areas is not None else 'supplied_incremental_areas_unverified',
        'reach_count': len(reaches), 'topological_order': order,
        'outlets': sorted(rid for rid, r in reaches.items() if r.get('downstream_id') is None),
        'reaches': [{'id': rid, 'downstream_id': reaches[rid].get('downstream_id'),
                    'upstream_ids': sorted(upstream[rid]), 'length_m': lengths[rid],
                    'incremental_catchment_area_m2': geometry_areas[rid] if geometry_areas is not None else reaches[rid].get('incremental_catchment_area_m2'),
                    'contributing_area_m2': areas[rid]} for rid in order],
        'limitations': ['Source rights, direction evidence and catchment disjointness require human verification.',
                        'Geometry checks do not establish real drainage divides or completeness; without geometry, areas assume disjoint catchments and missing area propagates as null.',
                        'One downstream reach only; bifurcation, tide/backwater and flow reversal are unsupported.',
                        'No discharge routing, water levels, barriers, land accessibility or inundation is computed.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    parser.add_argument('--raw-source', type=Path, required=True, help='Original source file whose SHA256 is declared in provenance')
    parser.add_argument('--tolerance-m', type=float, default=30)
    args = parser.parse_args()
    try:
        with args.package.open('rb') as f:
            raw = f.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError('Package exceeds 20 MB')
        report = audit_network(strict_json_loads(raw), args.tolerance_m)
        report['package_sha256'] = sha256(raw).hexdigest()
        digest = sha256()
        with args.raw_source.open('rb') as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b''):
                digest.update(chunk)
        if digest.hexdigest() != report['provenance']['raw_sha256']:
            raise ValueError('Original source checksum mismatch')
        report['raw_source_checksum'] = 'matched'
    except (ValueError, OSError) as e:
        parser.exit(2, f'Network rejected: {e}\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
