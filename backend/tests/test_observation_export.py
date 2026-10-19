"""Synthetic observation fixtures only. Actual HII export is exercised in Compose CI."""
from copy import deepcopy
from datetime import datetime,timezone
from hashlib import sha256
import csv
import io
import pytest
from app.hii_archive import SOURCE,DATUM
from app.observation_export import prepare_export,export_observations
from app.level_validation import load_series

START='2020-01-01T00:00:00Z';END='2020-01-01T00:30:00Z'


def inputs():
    station={'id':'HII:TEST_ONLY','source_id':SOURCE,'vertical_datum':DATUM,'source_url':'https://example.invalid/TEST_ONLY','license_evidence':'TEST_ONLY'}
    rows=[{'observed_at':f'2020-01-01T00:{minute:02}:00Z','value':value,'unit':'m','raw_sha256':'a'*64,
        'metadata':{'data_type':'historical_station_observation','source_quality_flag':'N',
        'timestamp_status':'assumed_timezone_source_has_no_offset','source_timezone':'Asia/Bangkok','source_url':'https://example.invalid/raw-TEST_ONLY.csv','source_line':i+2}} for i,(minute,value) in enumerate([(0,0),(20,-.25)])]
    return station,rows


def test_export_preserves_values_raw_hashes_timezone_assumptions_and_gaps():
    station,rows=inputs();original=deepcopy(rows)
    raw,d,p=prepare_export(station,rows,START,END,600,['N'])
    assert rows==original and d['raw_sha256']==sha256(raw).hexdigest()
    assert p['expected_intervals']==3 and p['exported_rows']==2 and p['absent_intervals']==1
    assert p['records'][0]['source_timezone']=='Asia/Bangkok'
    assert p['records'][0]['raw_sha256']=='a'*64
    assert d['datum_alignment']=='not_verified'
    parsed=list(csv.DictReader(io.StringIO(raw.decode())))
    assert [float(r['value_m']) for r in parsed]==[0,-.25]
    loaded=load_series(raw,d,{station['id']},datetime(2020,1,1,tzinfo=timezone.utc),datetime(2020,1,1,0,30,tzinfo=timezone.utc),600)
    assert len(loaded)==2 and loaded[(station['id'],2)]['value_m']==-.25


def test_bad_flag_blank_not_zero_and_metadata_cannot_override_identity():
    station,rows=inputs();rows[0]['metadata'].update(source_quality_flag='BAD',raw_sha256='spoof',observed_at='spoof')
    raw,d,p=prepare_export(station,rows,START,END,600,['N'])
    assert list(csv.DictReader(io.StringIO(raw.decode())))[0]['value_m']==''
    assert p['flag_rejected_rows']==1 and p['accepted_rows']==1
    assert p['records'][0]['raw_sha256']=='a'*64 and p['records'][0]['observed_at'].endswith('+00:00')


@pytest.mark.parametrize('mutation',[
    lambda s,r:s.update(source_id='UNKNOWN'),
    lambda s,r:s.update(vertical_datum='unknown'),
    lambda s,r:s.update(license_evidence=''),
    lambda s,r:r.clear(),
    lambda s,r:r.append(deepcopy(r[0])),
    lambda s,r:r[0].update(unit='ft'),
    lambda s,r:r[0].update(value=float('nan')),
    lambda s,r:r[0].update(raw_sha256='bad'),
    lambda s,r:r[0].update(observed_at='2020-01-01T00:01:00Z'),
    lambda s,r:r[0].update(observed_at=END),
    lambda s,r:r[0]['metadata'].pop('source_timezone'),
    lambda s,r:r[0]['metadata'].pop('source_quality_flag'),
    lambda s,r:r[0]['metadata'].update(data_type='forecast'),
])
def test_invalid_export_rejected(mutation):
    station,rows=inputs();mutation(station,rows)
    with pytest.raises(ValueError):prepare_export(station,rows,START,END,600,['N'])


def test_writes_new_directory_only_and_rejects_reuse(tmp_path,monkeypatch):
    import app.observation_export as module
    monkeypatch.setattr(module,'fetch_snapshot',lambda *a:inputs())
    target=tmp_path/'export'
    result=export_observations('HII:TEST_ONLY',START,END,600,['N'],target)
    assert result['simulation_generated'] is False and result['rows']==2
    assert sorted(p.name for p in target.iterdir())==['observations-descriptor.json','observations.csv','provenance.json']
    before=(target/'observations.csv').read_bytes()
    with pytest.raises(FileExistsError):export_observations('HII:TEST_ONLY',START,END,600,['N'],target)
    assert (target/'observations.csv').read_bytes()==before
