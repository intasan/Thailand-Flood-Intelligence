"""Integration tests run against isolated temporary schemas on real PostGIS."""
import json,os,uuid
from pathlib import Path
import psycopg
from psycopg.conninfo import make_conninfo
import pytest
from app.ingest import ingest
from app.repository import nearby_stations,data_status

@pytest.fixture
def database(monkeypatch):
    base=os.getenv('TEST_DATABASE_URL')
    if not base:pytest.skip('TEST_DATABASE_URL not configured')
    schema='test_'+uuid.uuid4().hex
    with psycopg.connect(base) as c:c.execute(f'CREATE SCHEMA {schema}')
    dsn=make_conninfo(base,options=f'-c search_path={schema},public')
    monkeypatch.setenv('DATABASE_URL',dsn)
    try:
        with psycopg.connect(dsn) as c:
            for migration in sorted((Path(__file__).parents[2]/'db').glob('*.sql')):
                c.execute(migration.read_text())
            c.execute("INSERT INTO sources VALUES ('TEST','TEST SOURCE','https://example.invalid','test license','approved')")
            c.execute("INSERT INTO stations(id,source_id,location,vertical_datum) VALUES ('TEST','TEST',ST_SetSRID(ST_MakePoint(100,13),4326),'TEST_DATUM')")
        yield dsn
    finally:
        with psycopg.connect(base) as c:c.execute(f'DROP SCHEMA {schema} CASCADE')

def test_idempotent_import_and_spatial_lookup(database,tmp_path):
    csv=tmp_path/'test.csv';manifest=tmp_path/'manifest.json'
    csv.write_text('station_id,observed_at,value,unit\nTEST,2020-01-01T00:00:00Z,1.25,m\n')
    manifest.write_text(json.dumps({'source_id':'TEST','source_url':'https://example.invalid','license_evidence':'test license','vertical_datum':'TEST_DATUM','approved_by':'TEST','approval_status':'approved'}))
    ingest(csv,manifest);ingest(csv,manifest)
    assert data_status()['observation_count']==1
    result=nearby_stations(13,100,1)['results'][0]
    assert result['value']==1.25 and result['freshness']=='stale'
    assert nearby_stations(14,101,1)['results']==[]

def test_atomic_rollback_unknown_station(database,tmp_path):
    csv=tmp_path/'test.csv';manifest=tmp_path/'manifest.json'
    csv.write_text('station_id,observed_at,value,unit\nTEST,2020-01-01T00:00:00Z,1,m\nUNKNOWN,2020-01-01T00:00:00Z,2,m\n')
    manifest.write_text(json.dumps({'source_id':'TEST','source_url':'https://example.invalid','license_evidence':'test license','vertical_datum':'TEST_DATUM','approved_by':'TEST','approval_status':'approved'}))
    with pytest.raises(ValueError):ingest(csv,manifest)
    assert data_status()['observation_count']==0

def test_hii_import_preserves_raw_provenance_and_series(database):
    from app.hii_archive import station_metadata,normalize,import_prepared
    from app.repository import observation_series
    raw=b'station_code,measure_datetime,water_level,quality_flag\nTEST_ONLY,2020-01-01 00:00:00,1,N\nTEST_ONLY,2020-01-01 00:10:00,-999,N\nTEST_ONLY,2020-01-01 00:20:00,2,N\n'
    meta='Station_Code,Station_Name,Latitude,Longitude,Station_Type_Name,Shared_data\nTEST_ONLY,TEST,13,100,ระดับน้ำ,แชร์ข้อมูล\n'.encode()
    s=station_metadata(meta,'TEST_ONLY');rows,report=normalize(raw,'TEST_ONLY','202001','Asia/Bangkok');report['source_url']='https://example.invalid/test-only.csv'
    first=import_prepared(s,rows,report);second=import_prepared(s,rows,report)
    assert first['inserted_rows']==2 and second['inserted_rows']==0
    result=observation_series('HII:TEST_ONLY')
    assert result['count']==2 and len(result['gaps'])==1
    assert result['results'][0]['raw_sha256']==report['raw_sha256']
    assert result['results'][0]['metadata']['timestamp_status'].startswith('assumed')

def test_revoked_source_disappears_from_public_counts_and_station_query(database):
    with psycopg.connect(database) as c:
        c.execute("INSERT INTO observations(station_id,observed_at,value,unit,raw_sha256) VALUES ('TEST','2020-01-01T00:00:00Z',1,'m','test')")
        c.execute("UPDATE sources SET approval_status='rejected' WHERE id='TEST'")
    status=data_status()
    assert status['station_count']==0 and status['observation_count']==0 and status['latest_observed_at'] is None
    assert nearby_stations(13,100,10)['results']==[]


def test_hii_export_read_only_snapshot_and_revocation(database,tmp_path):
    from app.observation_export import export_observations
    from app.hii_archive import SOURCE
    test_hii_import_preserves_raw_provenance_and_series(database)
    before=data_status()['observation_count']
    target=tmp_path/'export'
    result=export_observations('HII:TEST_ONLY','2019-12-31T17:00:00Z','2019-12-31T17:30:00Z',600,['N'],target)
    assert result['rows']==2 and result['absent_intervals']==1
    assert result['simulation_generated'] is False
    assert data_status()['observation_count']==before
    provenance=json.loads((target/'provenance.json').read_text())
    assert provenance['records'][0]['source_timezone']=='Asia/Bangkok'
    with psycopg.connect(database) as c:c.execute("UPDATE sources SET approval_status='rejected' WHERE id=%s",(SOURCE,))
    with pytest.raises(ValueError,match='Approved'):export_observations('HII:TEST_ONLY','2019-12-31T17:00:00Z','2019-12-31T17:30:00Z',600,['N'],tmp_path/'revoked')
    assert not (tmp_path/'revoked').exists()
