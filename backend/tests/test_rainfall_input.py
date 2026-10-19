"""Synthetic rainfall fixtures only. No measured rainfall or forecasts."""
from copy import deepcopy
from hashlib import sha256
import json
import subprocess
import sys
import pytest
from app.rainfall_input import prepare_rainfall
from test_catchments import catchments

HEADER='reach_id,start,end,rainfall_mm,quality_flag\n'
NETWORK_HASH='a'*64


def inputs():
    raw=(HEADER+''.join(f'{rid},2020-01-01T07:00:00+07:00,2020-01-01T08:00:00+07:00,{value},N\n' for rid,value in [('a',0),('b',2),('c',3)])).encode()
    m={'schema_version':1,'source_url':'https://example.invalid/TEST_ONLY','license':'TEST_ONLY',
       'license_evidence':'TEST_ONLY','dataset_version':'TEST_ONLY','retrieved_at':'2020-01-02T00:00:00Z',
       'spatial_averaging_evidence':'SYNTHETIC_TEST_ONLY','approval_status':'approved','approved_by':'TEST_ONLY',
       'data_type':'historical_observation','unit':'mm','quantity':'interval_accumulation','spatial_support':'catchment_mean',
       'raw_sha256':sha256(raw).hexdigest(),'network_package_sha256':NETWORK_HASH,
       'window_start':'2020-01-01T00:00:00Z','window_end':'2020-01-01T01:00:00Z',
       'interval_seconds':3600,'accepted_quality_flags':['N']}
    return raw,m,catchments()


def prepare(raw,m,n):
    m=deepcopy(m);m['raw_sha256']=sha256(raw).hexdigest()
    return prepare_rainfall(raw,m,n,NETWORK_HASH)


def test_complete_zero_rain_and_precipitation_volume():
    raw,m,n=inputs(); original=deepcopy(n)
    r=prepare_rainfall(raw,m,n,NETWORK_HASH)
    assert n==original
    assert r['status']=='prepared_complete'
    assert r['summaries'][0]['total_rainfall_mm']==0
    assert r['summaries'][0]['precipitation_volume_m3']==0
    b=r['summaries'][1]
    assert b['precipitation_volume_m3']==pytest.approx(b['incremental_catchment_area_m2']*.002)
    assert r['records'][0]['start']=='2020-01-01T00:00:00+00:00'
    assert r['network_raw_source_checksum']=='not_checked'
    assert r['validation']['hydraulic_validation']=='not_performed'
    assert 'discharge_m3_s' not in b


def test_absent_quarantined_and_empty_are_not_zero():
    raw,m,n=inputs()
    raw=raw.replace(b',2,N',b',2,BAD')
    m['window_end']='2020-01-01T02:00:00Z'
    r=prepare(raw,m,n)
    assert r['status']=='prepared_incomplete'
    for row in r['summaries']:
        assert row['total_rainfall_mm'] is None
        assert row['precipitation_volume_m3'] is None
        assert row['absent_intervals']==1
    assert r['summaries'][1]['known_interval_sum_mm'] is None
    assert r['summaries'][1]['quarantined_intervals']==1
    empty=prepare(HEADER.encode(),m,n)
    assert all(s['known_interval_sum_mm'] is None and s['absent_intervals']==2 for s in empty['summaries'])


@pytest.mark.parametrize('value',['','-999','-1','nan','inf','garbage'])
def test_invalid_amounts_quarantined_not_replaced(value):
    raw,m,n=inputs();raw=raw.replace(b',2,N',f',{value},N'.encode())
    r=prepare(raw,m,n)
    assert r['records'][1]['rainfall_mm'] is None
    assert r['summaries'][1]['total_rainfall_mm'] is None
    assert r['summaries'][1]['accepted_intervals']==0


@pytest.mark.parametrize('mutation',[
    lambda m:m.update(data_type='forecast'),
    lambda m:m.update(window_start='2099-01-01T00:00:00Z',window_end='2099-01-01T01:00:00Z'),
    lambda m:m.update(unit='mm/h'),
    lambda m:m.update(quantity='cumulative_counter'),
    lambda m:m.update(spatial_support='station_point'),
    lambda m:m.update(approval_status='pending'),
    lambda m:m.update(license_evidence=''),
    lambda m:m.update(accepted_quality_flags=[]),
    lambda m:m.update(accepted_quality_flags=['N','N']),
    lambda m:m.update(interval_seconds=True),
    lambda m:m.update(interval_seconds=59),
    lambda m:m.update(window_end='2020-02-02T00:00:00Z'),
    lambda m:m.update(window_start='2020-01-01T00:00:00'),
    lambda m:m.update(window_end='2020-01-01T00:30:00Z'),
    lambda m:m.update(raw_sha256='0'*64),
    lambda m:m.update(network_package_sha256='0'*64),
    lambda m:m.update(schema_version=True),
])
def test_bad_manifest_rejected(mutation):
    raw,m,n=inputs();mutation(m)
    with pytest.raises(ValueError):prepare_rainfall(raw,m,n,NETWORK_HASH)


@pytest.mark.parametrize('change',[
    lambda r:r.replace(b'a,',b'unknown,',1),
    lambda r:r+r.splitlines(keepends=True)[1],
    lambda r:r.replace(b'07:00:00+07:00',b'07:30:00+07:00',1),
    lambda r:r.replace(b'07:00:00+07:00',b'07:00:00',1),
    lambda r:r.replace(b'08:00:00+07:00',b'09:00:00+07:00',1),
    lambda r:r.replace(b'quality_flag',b'flag'),
    lambda r:r.replace(b',0,N',b',0,N,extra'),
    lambda r:r+b'\xff',
])
def test_bad_csv_rejected(change):
    raw,m,n=inputs()
    with pytest.raises(ValueError):prepare(change(raw),m,n)


def test_missing_catchments_and_interval_limit_rejected(monkeypatch):
    raw,m,n=inputs()
    for reach in n['reaches']:reach.pop('incremental_catchment_geometry')
    with pytest.raises(ValueError,match='catchment'):prepare(raw,m,n)
    import app.rainfall_input as module
    monkeypatch.setattr(module,'MAX_INTERVALS',2)
    with pytest.raises(ValueError,match='expected'):prepare(raw,m,catchments())


def test_overflow_rejected():
    raw,m,n=inputs();raw=raw.replace(b',2,N',b',1e308,N')
    with pytest.raises(ValueError,match='overflow'):prepare(raw,m,n)


def test_cli_checks_original_network_and_manifest_hash(tmp_path):
    raw,m,n=inputs();source=tmp_path/'raw.bin';source.write_bytes(b'SYNTHETIC_NETWORK_ONLY')
    n['provenance']['raw_sha256']=sha256(source.read_bytes()).hexdigest()
    network=tmp_path/'network.json';network.write_text(json.dumps(n))
    m['network_package_sha256']=sha256(network.read_bytes()).hexdigest()
    csv=tmp_path/'rain.csv';csv.write_bytes(raw)
    manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps(m))
    cmd=[sys.executable,'-m','app.rainfall_input',str(csv),str(manifest),'--network',str(network),'--network-raw-source',str(source)]
    result=subprocess.run(cmd,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    report=json.loads(result.stdout)
    assert report['manifest_sha256']==sha256(manifest.read_bytes()).hexdigest()
    assert report['network_raw_source_checksum']=='matched'
    source.write_bytes(b'changed')
    rejected=subprocess.run(cmd,capture_output=True,text=True)
    assert rejected.returncode==2 and not rejected.stdout


def test_two_interval_totals_and_partial_sum_remains_distinct():
    raw,m,n=inputs()
    second=''.join(f'{rid},2020-01-01T01:00:00Z,2020-01-01T02:00:00Z,4,N\n' for rid in ['c','b','a']).encode()
    raw+=second;m['window_end']='2020-01-01T02:00:00Z'
    report=prepare(raw,m,n)
    assert report['status']=='prepared_complete'
    assert [s['total_rainfall_mm'] for s in report['summaries']]==[4,6,7]
    incomplete=prepare(raw.replace(b'b,2020-01-01T01:00:00Z,2020-01-01T02:00:00Z,4,N',b'b,2020-01-01T01:00:00Z,2020-01-01T02:00:00Z,,N'),m,n)
    b=incomplete['summaries'][1]
    assert b['known_interval_sum_mm']==2 and b['total_rainfall_mm'] is None
    assert b['absent_intervals']==0 and b['quarantined_intervals']==1


def test_equivalent_timezone_duplicate_rejected():
    raw,m,n=inputs()
    raw+=b'a,2020-01-01T00:00:00Z,2020-01-01T01:00:00Z,0,N\n'
    with pytest.raises(ValueError,match='duplicate'):prepare(raw,m,n)
