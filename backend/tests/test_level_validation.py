"""Synthetic series only, never real gauges or calibrated model outputs."""
from copy import deepcopy
from hashlib import sha256
import json
import math
import subprocess
import sys
import pytest
from app.level_validation import compare_levels

HEADER='station_id,observed_at,value_m,quality_flag\n'


def series(values):
    return (HEADER+''.join(f'TEST,2020-01-01T0{i}:00:00Z,{v},N\n' for i,v in enumerate(values))).encode()


def inputs():
    obs,sim=series([1,2,3]),series([2,1,5])
    common={'vertical_datum':'SYNTHETIC_DATUM_ONLY','unit':'m','quantity':'water_surface_elevation','accepted_quality_flags':['N']}
    manifest={'schema_version':1,'event_id':'SYNTHETIC_VALIDATION','calibration_event_ids':['SYNTHETIC_CALIBRATION'],
        'datum_alignment_evidence':'SYNTHETIC_TEST_ONLY','station_ids':['TEST'],'window_start':'2020-01-01T00:00:00Z',
        'window_end':'2020-01-01T03:00:00Z','interval_seconds':3600,
        'observations':{**common,'source_url':'https://example.invalid/TEST_ONLY','license':'TEST_ONLY','license_evidence':'TEST_ONLY',
            'dataset_version':'TEST_ONLY','retrieved_at':'2020-01-02T00:00:00Z','raw_sha256':sha256(obs).hexdigest()},
        'simulations':{**common,'model_name':'SYNTHETIC_TEST_ONLY','model_version':'TEST_ONLY','run_id':'TEST_ONLY',
            'generated_at':'2020-01-02T00:00:00Z','configuration_sha256':'a'*64,'raw_sha256':sha256(sim).hexdigest()}}
    return obs,sim,manifest


def compare(obs,sim,m):
    m=deepcopy(m);m['observations']['raw_sha256']=sha256(obs).hexdigest();m['simulations']['raw_sha256']=sha256(sim).hexdigest()
    return compare_levels(obs,sim,m)


def test_known_errors_bias_sign_and_no_approval():
    obs,sim,m=inputs();original=deepcopy(m);r=compare_levels(obs,sim,m)
    assert m==original and r['status']=='comparison_complete'
    metrics=r['stations'][0]['paired_metrics']
    assert metrics==pytest.approx({'mae_m':4/3,'rmse_m':math.sqrt(2),'bias_m':2/3,'max_abs_error_m':2})
    assert r['acceptance_decision']=='not_assessed_no_thresholds_or_reviewer'
    assert r['scientific_validation']=='not_certified'
    assert r['error_sign']=='simulated_minus_observed'


def test_missing_and_quarantined_values_are_never_zero_filled():
    obs,sim,m=inputs();obs=series([1,'',3]);sim=series([2,1])
    r=compare(obs,sim,m);s=r['stations'][0]
    assert r['status']=='comparison_incomplete'
    assert s['accepted_pairs']==1 and s['paired_metrics'] is None
    assert s['quarantined_observations']==1 and s['absent_simulations']==1
    assert s['metrics_scope']=='accepted_pairs_only_incomplete_window'


def test_partial_metrics_explicit_and_negative_zero_levels_valid():
    obs,sim,m=inputs();r=compare(series([-2,0]),series([-1,0]),m)
    s=r['stations'][0]
    assert s['complete'] is False and s['accepted_pairs']==2
    assert s['paired_metrics']['mae_m']==.5
    assert s['absent_observations']==1 and s['absent_simulations']==1


def test_equivalent_offsets_match_exactly_and_unordered_rows_work():
    obs,sim,m=inputs()
    sim=sim.replace(b'2020-01-01T00:00:00Z',b'2020-01-01T07:00:00+07:00')
    lines=sim.splitlines(keepends=True);sim=lines[0]+b''.join(reversed(lines[1:]))
    assert compare(obs,sim,m)['status']=='comparison_complete'
    sim+=b'TEST,2020-01-01T00:00:00Z,2,N\n'
    with pytest.raises(ValueError,match='Duplicate'):compare(obs,sim,m)


def test_empty_files_report_incomplete_without_fake_metrics():
    obs,sim,m=inputs();r=compare(HEADER.encode(),HEADER.encode(),m)
    assert r['pooled_accepted_pairs']==0 and r['pooled_paired_metrics'] is None
    assert r['stations'][0]['absent_observations']==3


@pytest.mark.parametrize('value',['nan','inf','nonsense'])
def test_bad_value_quarantined(value):
    obs,sim,m=inputs();r=compare(series([1,value,3]),sim,m)
    assert r['stations'][0]['quarantined_observations']==1
    assert r['stations'][0]['accepted_pairs']==2


@pytest.mark.parametrize('change',[
    lambda m:m.update(event_id='SYNTHETIC_CALIBRATION'),
    lambda m:m.update(calibration_event_ids=None),
    lambda m:m.update(station_ids=['TEST','TEST']),
    lambda m:m.update(interval_seconds=True),
    lambda m:m.update(window_end='2020-02-02T00:00:00Z'),
    lambda m:m.update(window_start='2020-01-01T00:00:00'),
    lambda m:m.update(datum_alignment_evidence=''),
    lambda m:m['observations'].update(license_evidence=''),
    lambda m:m['observations'].update(unit='ft'),
    lambda m:m['simulations'].update(quantity='relative_gauge_stage'),
    lambda m:m['simulations'].update(vertical_datum='DIFFERENT_TEST_DATUM'),
    lambda m:m['simulations'].update(configuration_sha256='bad'),
    lambda m:m['observations'].update(raw_sha256='0'*64),
    lambda m:m['observations'].update(accepted_quality_flags=[]),
])
def test_bad_manifest_rejected(change):
    obs,sim,m=inputs();change(m)
    with pytest.raises(ValueError):compare_levels(obs,sim,m)


@pytest.mark.parametrize('change',[
    lambda raw:raw.replace(b'TEST,',b'UNKNOWN,',1),
    lambda raw:raw.replace(b'00:00:00Z',b'00:30:00Z',1),
    lambda raw:raw.replace(b'00:00:00Z',b'00:00:00',1),
    lambda raw:raw.replace(b'2020-01-01T00:00:00Z',b'2020-01-02T00:00:00Z',1),
    lambda raw:raw.replace(b'value_m',b'value'),
    lambda raw:raw.replace(b',1,N',b',1,N,extra',1),
])
def test_bad_csv_rejected(change):
    obs,sim,m=inputs()
    with pytest.raises(ValueError):compare(change(obs),sim,m)


def test_source_flag_and_numeric_overflow(tmp_path):
    obs,sim,m=inputs();obs=obs.replace(b',2,N',b',2,BAD')
    assert compare(obs,sim,m)['stations'][0]['quarantined_observations']==1
    with pytest.raises(ValueError,match='overflow'):compare(series([-1e308,0,0]),series([1e308,0,0]),m)


def test_multiple_stations_pooled_by_pairs_and_capacity(monkeypatch):
    obs,sim,m=inputs();m['station_ids'].append('OTHER')
    obs+=series([0,0,0]).split(b'\n',1)[1].replace(b'TEST,',b'OTHER,')
    sim+=series([0,0,0]).split(b'\n',1)[1].replace(b'TEST,',b'OTHER,')
    r=compare(obs,sim,m)
    assert r['pooled_accepted_pairs']==6
    assert r['pooled_paired_metrics']['mae_m']==pytest.approx(2/3)
    import app.level_validation as module
    monkeypatch.setattr(module,'MAX_PAIRS',5)
    with pytest.raises(ValueError,match='expected'):compare(obs,sim,m)


def test_cli_hash_and_rejects_mismatch_without_stdout(tmp_path):
    obs,sim,m=inputs();o=tmp_path/'obs.csv';s=tmp_path/'sim.csv';p=tmp_path/'manifest.json'
    o.write_bytes(obs);s.write_bytes(sim);p.write_text(json.dumps(m))
    cmd=[sys.executable,'-m','app.level_validation',str(o),str(s),str(p)]
    r=subprocess.run(cmd,capture_output=True,text=True)
    assert r.returncode==0,r.stderr
    assert json.loads(r.stdout)['manifest_sha256']==sha256(p.read_bytes()).hexdigest()
    s.write_bytes(sim+b'\n')
    r=subprocess.run(cmd,capture_output=True,text=True)
    assert r.returncode==2 and not r.stdout
