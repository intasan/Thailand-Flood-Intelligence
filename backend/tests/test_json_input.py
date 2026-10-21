"""Ambiguous/malformed metadata never becomes accepted source evidence."""
import json
import pytest
from app.json_input import strict_json_loads,read_json_object


@pytest.mark.parametrize('raw',[
    b'{"license":"one","license":"two"}',
    b'{"source":{"raw_sha256":"one","raw_sha256":"two"}}',
    b'{"license":"one","\\u006cicense":"two"}',
    b'{"value":NaN}',b'{"value":Infinity}',b'{"value":-Infinity}',
    b'{"value":1e400}',b'{"value":-1e400}',
    b'[]',b'null',b'1',b'"string"',b'{"x":1} trailing',b'{"x":"\xff"}',
])
def test_invalid_json_objects_rejected(raw):
    with pytest.raises(ValueError):strict_json_loads(raw)


def test_valid_metadata_bom_strings_escapes_and_false_zero_preserved():
    data={'nested':{'value':0,'negative':-.25,'flag':False,'missing':None},'text':'ไทย { [ ] } " \\','number':1e30}
    raw=b'\xef\xbb\xbf'+json.dumps(data,ensure_ascii=False).encode()
    assert strict_json_loads(raw)==data
    assert strict_json_loads(json.dumps(data))==data


def test_depth_limit_tracks_containers_not_quoted_characters():
    assert strict_json_loads('{"text":"'+('['*500)+'"}',max_depth=2)['text']=='['*500
    raw='{"x":'+('['*64)+'0'+(']'*64)+'}'
    with pytest.raises(ValueError,match='depth'):strict_json_loads(raw)
    raw='{"x":'+('['*63)+'0'+(']'*63)+'}'
    assert isinstance(strict_json_loads(raw)['x'],list)


def test_utf8_byte_limit_and_bounded_file_read(tmp_path):
    raw='{"text":"ไทย"}'.encode()
    assert strict_json_loads(raw,max_bytes=len(raw))['text']=='ไทย'
    with pytest.raises(ValueError,match='byte limit'):strict_json_loads(raw,max_bytes=len(raw)-1)
    path=tmp_path/'manifest.json';path.write_bytes(raw)
    with pytest.raises(ValueError,match='byte limit'):read_json_object(path,max_bytes=len(raw)-1)
    assert read_json_object(path,max_bytes=len(raw))['text']=='ไทย'


def test_ingestion_and_signed_evidence_share_duplicate_rejection(tmp_path):
    from app.ingest import load_rows
    from app.model_evidence import strict_json,EvidenceRejected
    manifest=tmp_path/'manifest.json';manifest.write_text('{"approval_status":"pending","approval_status":"approved"}')
    csv=tmp_path/'data.csv';csv.write_text('station_id,observed_at,value,unit\n')
    with pytest.raises(ValueError,match='Duplicate'):load_rows(csv,manifest)
    with pytest.raises(EvidenceRejected,match='Duplicate'):strict_json(manifest)


@pytest.mark.parametrize('module,args',[
    ('river_network',['bad.json','--raw-source','source.bin']),
    ('dem_audit',['raster.tif','bad.json']),
    ('rainfall_input',['data.csv','bad.json','--network','network.json','--network-raw-source','source.bin']),
    ('level_validation',['data.csv','data.csv','bad.json']),
    ('pilot_preflight',['bad.json']),
])
def test_operator_clis_reject_duplicate_metadata_before_success_output(tmp_path,module,args):
    import subprocess,sys
    (tmp_path/'bad.json').write_text('{"schema_version":0,"schema_version":1}')
    for p in ['source.bin','raster.tif','data.csv','network.json']:(tmp_path/p).write_text('TEST_ONLY')
    command=[sys.executable,'-m','app.'+module,*[str(tmp_path/a) if a in {'bad.json','source.bin','raster.tif','data.csv','network.json'} else a for a in args]]
    result=subprocess.run(command,capture_output=True,text=True)
    assert result.returncode==2 and not result.stdout
    assert 'Duplicate JSON key' in result.stderr


@pytest.mark.parametrize('raw',[b'{"text":"\\ud800"}',b'{"\\udfff":0}'])
def test_unpaired_surrogates_rejected_before_output_encoding(raw):
    with pytest.raises(ValueError,match='surrogate'):strict_json_loads(raw)


def test_paired_surrogate_emoji_is_valid():
    assert strict_json_loads(b'{"text":"\\ud83d\\ude00"}')['text']=='😀'
