import json
import pytest
from app.ingest import load_rows

def test_manifest_gate_and_checksum(tmp_path):
    c=tmp_path/'rows.csv';m=tmp_path/'manifest.json'
    c.write_text('station_id,observed_at,value,unit\nTEST_ONLY,2020-01-01T00:00:00Z,1.2,m\n')
    metadata=dict(source_id='TEST_ONLY',license_evidence='unit-test fixture',vertical_datum='TEST',source_url='https://example.invalid',approved_by='test',approval_status='pending')
    m.write_text(json.dumps(metadata))
    with pytest.raises(ValueError):load_rows(c,m)
    metadata['approval_status']='approved';m.write_text(json.dumps(metadata))
    _,rows,digest=load_rows(c,m)
    assert len(rows)==1 and len(digest)==64

def test_bad_unit_rejected(tmp_path):
    c=tmp_path/'rows.csv';m=tmp_path/'manifest.json'
    c.write_text('station_id,observed_at,value,unit\nTEST,2020-01-01T00:00:00Z,1,cm\n')
    m.write_text(json.dumps(dict(source_id='test',license_evidence='fixture',vertical_datum='TEST',source_url='https://example.invalid',approved_by='test',approval_status='approved')))
    with pytest.raises(ValueError):load_rows(c,m)
