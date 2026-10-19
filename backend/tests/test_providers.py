import httpx
import pytest
from app.providers import geocode,elevation,ProviderUnavailable

@pytest.fixture(autouse=True)
def cache(tmp_path,monkeypatch):
    monkeypatch.setenv('PROVIDER_CACHE_PATH',str(tmp_path/'cache.sqlite'))
    monkeypatch.setenv('PUBLIC_DATA_ENABLED','true')

def test_search_filters_country_and_caches():
    calls=[]
    def handler(req):
        calls.append(req)
        assert req.url.params['countryCode']=='TH'
        return httpx.Response(200,json={'results':[{'id':1,'name':'TEST','country_code':'TH','latitude':13,'longitude':100},{'id':2,'name':'WRONG','country_code':'DE','latitude':51,'longitude':13}]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        first=geocode('TEST',client);second=geocode('TEST',client)
    assert len(calls)==1 and len(first['results'])==1 and second['metadata']['cached']

def test_provider_failure_never_becomes_fake_elevation():
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(503))) as client:
        with pytest.raises(ProviderUnavailable):elevation(13,100,client)

@pytest.mark.parametrize('value',[None,5])
def test_surface_is_not_ground(value):
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'elevation':[value]}))) as client:
        result=elevation(13,100,client)
    assert result['value_m']==value and result['data_type']=='digital_surface_model'
    assert result['resolution_m']==90 and result['metadata']['observed_at'] is None

def test_budget_shared_across_client_instances(tmp_path,monkeypatch):
    import sqlite3,time
    db=tmp_path/'cache.sqlite';monkeypatch.setenv('PROVIDER_CACHE_PATH',str(db))
    with sqlite3.connect(db) as c:
        c.execute('CREATE TABLE quota(bucket TEXT PRIMARY KEY,count INTEGER NOT NULL)')
        c.execute('INSERT INTO quota VALUES (?,500)',(f'day:{int(time.time()//86400)}',))
    with pytest.raises(ProviderUnavailable):elevation(13,100)

def test_malformed_upstream_never_poisoned_cache():
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(200,json={'elevation':['wrong']} if len(calls)==1 else {'elevation':[12]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderUnavailable):elevation(13,100,client)
        result=elevation(13,100,client)
    assert result['value_m']==12 and len(calls)==2

def test_preexisting_bad_cache_is_evicted(tmp_path):
    import sqlite3,time,json,hashlib
    path=tmp_path/'cache.sqlite';key=hashlib.sha256(json.dumps(['elevation',{'latitude':13,'longitude':100}],sort_keys=True).encode()).hexdigest()
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE cache(key TEXT PRIMARY KEY,body TEXT NOT NULL,fetched REAL NOT NULL)')
        db.execute('INSERT INTO cache VALUES (?,?,?)',(key,json.dumps({'elevation':'bad'}),time.time()))
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'elevation':[8]}))) as client:
        result=elevation(13,100,client)
    assert result['value_m']==8 and result['metadata']['cached'] is False

def test_invalid_admin_object_rejected_before_ui_can_receive_it():
    bad={'results':[{'id':1,'name':'TEST','country_code':'TH','latitude':13,'longitude':100,'admin1':{'unexpected':'object'}}]}
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=bad))) as client:
        with pytest.raises(ProviderUnavailable):geocode('TEST',client)
