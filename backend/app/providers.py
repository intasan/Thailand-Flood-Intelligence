"""Open-Meteo research adapters. Cached, bounded, no fabricated fallback."""
from .json_input import strict_json_loads
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import time
import httpx

class ProviderUnavailable(Exception): pass


def validate_payload(kind,payload):
    if not isinstance(payload,dict) or payload.get('error'):raise ValueError('Invalid upstream data')
    if kind=='geocode':
        rows=payload.get('results',[])
        if not isinstance(rows,list) or len(rows)>100:raise ValueError('Invalid result list')
        for row in rows:
            if not isinstance(row,dict):raise ValueError('Invalid location')
            if row.get('country_code')!='TH':continue
            if isinstance(row.get('id'),bool) or not isinstance(row.get('id'),int):raise ValueError('Invalid location ID')
            if not isinstance(row.get('name'),str) or not row['name'] or len(row['name'])>500:raise ValueError('Invalid location name')
            for field in ('admin1','admin2'):
                if row.get(field) is not None and not isinstance(row[field],str):raise ValueError('Invalid admin name')
            for field,limit in (('latitude',90),('longitude',180)):
                v=row.get(field)
                if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or abs(v)>limit:raise ValueError('Invalid location coordinate')
    elif kind=='elevation':
        values=payload.get('elevation')
        if not isinstance(values,list) or len(values)!=1:raise ValueError('Invalid elevation list')
        value=values[0]
        if value is not None and (isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value)):raise ValueError('Invalid elevation value')
    else:raise ValueError('Unknown provider kind')
    return payload


def request_json(kind, params, client=None):
    if os.getenv('PUBLIC_DATA_ENABLED', 'true').lower()!='true':
        raise ProviderUnavailable('Public research data disabled')
    urls={'geocode':'https://geocoding-api.open-meteo.com/v1/search','elevation':'https://api.open-meteo.com/v1/elevation'}
    key=hashlib.sha256(json.dumps([kind,params],sort_keys=True).encode()).hexdigest()
    path=Path(os.getenv('PROVIDER_CACHE_PATH','/tmp/flood-provider-cache.sqlite'))
    path.parent.mkdir(parents=True,exist_ok=True)
    now=time.time()
    with sqlite3.connect(path,timeout=3) as db:
        db.execute('CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, body TEXT NOT NULL, fetched REAL NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS quota (bucket TEXT PRIMARY KEY, count INTEGER NOT NULL)')
        hit=db.execute('SELECT body,fetched FROM cache WHERE key=? AND fetched>?',(key,now-86400*7)).fetchone()
        if hit:
            try:return validate_payload(kind,strict_json_loads(hit[0],max_bytes=1_000_000)),datetime.fromtimestamp(hit[1],timezone.utc).isoformat(),True
            except (ValueError,TypeError):
                db.execute('DELETE FROM cache WHERE key=?',(key,))
                db.commit()
        db.execute('BEGIN IMMEDIATE')
        # Shared SQLite file enforces quotas across workers on a single deployment.
        for bucket,limit in ((f'minute:{int(now//60)}',30),(f'day:{int(now//86400)}',500)):
            count=db.execute('SELECT count FROM quota WHERE bucket=?',(bucket,)).fetchone()
            if count and count[0]>=limit:raise ProviderUnavailable('Research provider request budget exhausted')
            db.execute('INSERT INTO quota VALUES (?,1) ON CONFLICT(bucket) DO UPDATE SET count=count+1',(bucket,))
        db.commit()
    try:
        if client is None:
            with httpx.Client(timeout=10,follow_redirects=False,headers={'User-Agent':'Thailand-Flood-Intelligence/0.5 (+https://github.com/intasan/Thailand-Flood-Intelligence)'}) as c:
                response=c.get(urls[kind],params=params)
        else:response=client.get(urls[kind],params=params)
        response.raise_for_status()
        if len(response.content)>1_000_000:raise ValueError('Upstream payload too large')
        payload=validate_payload(kind,strict_json_loads(response.content,max_bytes=1_000_000))
    except (httpx.HTTPError,ValueError,KeyError) as e:
        raise ProviderUnavailable('Upstream data unavailable; no substitute values used') from e
    with sqlite3.connect(path,timeout=3) as db:
        db.execute('INSERT OR REPLACE INTO cache VALUES (?,?,?)',(key,json.dumps(payload),now))
        db.execute('DELETE FROM cache WHERE fetched<?',(now-86400*7,))
        db.execute("DELETE FROM quota WHERE bucket NOT IN (?,?)",(f'minute:{int(now//60)}',f'day:{int(now//86400)}'))
    return payload,datetime.fromtimestamp(now,timezone.utc).isoformat(),False


def geocode(q,client=None):
    payload,fetched,cached=request_json('geocode',{'name':q.strip(),'count':8,'language':'th','countryCode':'TH'},client)
    results=[]
    try:
        rows=payload.get('results',[])
        if not isinstance(rows,list):raise ValueError()
        for row in rows:
            if not isinstance(row,dict):raise ValueError()
            if row.get('country_code')!='TH':continue
            lat,lon=float(row['latitude']),float(row['longitude'])
            if not math.isfinite(lat) or not math.isfinite(lon) or not (-90<=lat<=90 and -180<=lon<=180):raise ValueError()
            results.append({'id':row['id'],'name':str(row['name']),'admin1':row.get('admin1'),'admin2':row.get('admin2'),'lat':lat,'lon':lon})
    except (KeyError,TypeError,ValueError) as e:raise ProviderUnavailable('Malformed geocoding response') from e
    return {'results':results,'metadata':{'fetched_at':fetched,'cached':cached,'source':'GeoNames via Open-Meteo','source_url':'https://open-meteo.com/en/docs/geocoding-api','attribution':'GeoNames / Open-Meteo','license_url':'https://open-meteo.com/en/licence'},'limitations':['ค้นหาชุมชน/เมืองและรหัสไปรษณีย์ ไม่รับประกันที่อยู่รายบ้าน ใช้หมุดหรือ GPS เพื่อระบุที่ดิน']}


def elevation(lat,lon,client=None):
    payload,fetched,cached=request_json('elevation',{'latitude':lat,'longitude':lon},client)
    try:
        values=payload['elevation']
        if len(values)!=1:raise ValueError()
        v=values[0]
        if v is not None and (isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v)):raise ValueError()
    except (KeyError,TypeError,ValueError) as e:raise ProviderUnavailable('Malformed elevation response') from e
    return {'value_m':v,'status':'available' if v is not None else 'no_data','data_type':'digital_surface_model',
        'resolution_m':90,'vertical_datum':'EGM2008','dataset':'Copernicus DEM 2021 GLO-90',
        'metadata':{'fetched_at':fetched,'cached':cached,'observed_at':None,'dataset_release':'2021','source_url':'https://open-meteo.com/en/docs/elevation-api','attribution':'Copernicus / Open-Meteo','normalized_payload_sha256':hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()},
        'limitations':['ความสูงพื้นผิวประมาณ 90 เมตร อาจรวมอาคารและต้นไม้ ไม่ใช่ค่ารังวัดพื้นดินรายบ้าน','ห้ามลบระดับสถานีน้ำเพื่อสรุปความลึกน้ำท่วมโดยตรง']}
