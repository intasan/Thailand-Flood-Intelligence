"""Synthetic fixtures only, not Thai river data or model output."""
from copy import deepcopy
import json
import subprocess
import sys
import pytest
from app.river_network import audit_network


def package():
    def reach(rid, target, coords, area):
        return {'id': rid, 'downstream_id': target, 'geometry': {'type': 'LineString', 'coordinates': coords}, 'incremental_catchment_area_m2': area}
    return {'schema_version': 1, 'crs': 'EPSG:4326', 'provenance': {
        'source_url': 'https://example.invalid/TEST_ONLY', 'license': 'TEST_ONLY', 'license_evidence': 'TEST_ONLY',
        'retrieved_at': '2020-01-01T00:00:00Z', 'dataset_version': 'TEST_ONLY', 'raw_sha256': '0'*64,
        'direction_evidence': 'SYNTHETIC_TEST_ONLY'}, 'reaches': [
        reach('a', 'c', [[100, 15.01], [100, 15]], 10),
        reach('b', 'c', [[100.01, 15.01], [100, 15]], 20),
        reach('c', None, [[100, 15], [100, 14.99]], 30)]}


def test_confluence_and_unknown_area():
    p = package(); original = deepcopy(p)
    report = audit_network(p)
    assert p == original
    assert report['outlets'] == ['c']
    assert report['reaches'][-1]['contributing_area_m2'] == 60
    assert report['reaches'][-1]['upstream_ids'] == ['a', 'b']
    assert all(r['length_m'] > 0 for r in report['reaches'])
    assert report['hydraulic_validation'] == 'not_performed'
    assert 'flood_depth_m' not in report
    p['reaches'][0]['incremental_catchment_area_m2'] = None
    assert audit_network(p)['reaches'][-1]['contributing_area_m2'] is None
    p['reaches'][0]['incremental_catchment_area_m2'] = 0
    assert audit_network(p)['reaches'][-1]['contributing_area_m2'] == 50


@pytest.mark.parametrize('mutation', [
    lambda p: p['reaches'].append(deepcopy(p['reaches'][0])),
    lambda p: p['reaches'][0].update(downstream_id='missing'),
    lambda p: p['reaches'][0].update(downstream_id='a'),
    lambda p: p['reaches'][0]['geometry']['coordinates'].reverse(),
    lambda p: p['reaches'][0].update(incremental_catchment_area_m2=float('nan')),
    lambda p: p['reaches'][0].update(incremental_catchment_area_m2=True),
    lambda p: p['reaches'][0]['geometry'].update(coordinates=[[100, 15, 0], [100, 15]]),
    lambda p: p['reaches'][0]['geometry'].update(coordinates=[[100, 15], [100, 15]]),
    lambda p: p['provenance'].update(license_evidence=''),
    lambda p: p['provenance'].update(retrieved_at='2020-01-01'),
    lambda p: p.update(crs='EPSG:3857'),
    lambda p: p['reaches'][0].pop('downstream_id'),
])
def test_invalid_networks_fail_closed(mutation):
    p = package(); mutation(p)
    with pytest.raises(ValueError): audit_network(p)


def test_cycles_rejected_even_with_connected_endpoints():
    p = package(); p['reaches'] = p['reaches'][:1]
    a = p['reaches'][0]; a['downstream_id'] = 'b'
    b = deepcopy(a); b['id'] = 'b'; b['downstream_id'] = 'a'; b['geometry']['coordinates'].reverse()
    p['reaches'].append(b)
    with pytest.raises(ValueError, match='cycle'): audit_network(p)


def test_separate_outlets_are_not_invented_connections():
    p = package(); p['reaches'][0]['downstream_id'] = None
    assert audit_network(p)['outlets'] == ['a', 'c']


def test_cli_hash_and_bad_json(tmp_path):
    from hashlib import sha256
    source = tmp_path / 'raw.bin'; source.write_bytes(b'SYNTHETIC_TEST_ONLY')
    p = package(); p['provenance']['raw_sha256'] = sha256(source.read_bytes()).hexdigest()
    path = tmp_path / 'network.json'; path.write_text(json.dumps(p))
    result = subprocess.run([sys.executable, '-m', 'app.river_network', str(path), '--raw-source', str(source)], capture_output=True, text=True)
    assert result.returncode == 0
    assert json.loads(result.stdout)['package_sha256'] == sha256(path.read_bytes()).hexdigest()
    assert json.loads(result.stdout)['raw_source_checksum'] == 'matched'
    source.write_bytes(b'changed')
    mismatch = subprocess.run([sys.executable, '-m', 'app.river_network', str(path), '--raw-source', str(source)], capture_output=True, text=True)
    assert mismatch.returncode == 2 and not mismatch.stdout
    path.write_text('{')
    bad = subprocess.run([sys.executable, '-m', 'app.river_network', str(path), '--raw-source', str(source)], capture_output=True, text=True)
    assert bad.returncode == 2 and not bad.stdout


def test_tolerance_and_extreme_numbers_rejected():
    for value in [-1, 1001, True, float('inf')]:
        with pytest.raises(ValueError): audit_network(package(), value)
    for value in [10**1000, -1, float('inf')]:
        p = package(); p['reaches'][0]['incremental_catchment_area_m2'] = value
        with pytest.raises(ValueError): audit_network(p)
    p = package(); p['schema_version'] = True
    with pytest.raises(ValueError): audit_network(p)


def test_endpoint_gap_respects_configured_tolerance_without_snapping():
    p = package(); p['reaches'][0]['geometry']['coordinates'][-1][1] += .0001
    with pytest.raises(ValueError, match='gap'): audit_network(p, 0)
    report = audit_network(p, 30)
    assert report['endpoint_tolerance_m'] == 30
    assert p['reaches'][0]['geometry']['coordinates'][-1][1] == 15.0001


def test_long_chain_uses_iterative_traversal():
    p = package()
    p['reaches'] = [{'id': str(i), 'downstream_id': str(i+1) if i < 1099 else None,
        'geometry': {'type': 'LineString', 'coordinates': [[100, 16-i*.0001], [100, 16-(i+1)*.0001]]},
        'incremental_catchment_area_m2': 1} for i in range(1100)]
    r = audit_network(p)
    assert r['reaches'][-1]['contributing_area_m2'] == 1100
    assert len(r['topological_order']) == 1100
