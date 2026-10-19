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
            c.execute((Path(__file__).parents[2]/'db/001_init.sql').read_text())
            c.execute("INSERT INTO sources VALUES ('TEST','TEST SOURCE','https://example.invalid','test license','approved')")
            c.execute("INSERT INTO stations VALUES ('TEST','TEST',ST_SetSRID(ST_MakePoint(100,13),4326),'TEST_DATUM')")
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
