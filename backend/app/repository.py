from datetime import datetime, timezone
import os
import psycopg
from psycopg.rows import dict_row


def connect():return psycopg.connect(os.environ['DATABASE_URL'],connect_timeout=3,row_factory=dict_row)


def data_status():
    with connect() as c:
        observations=c.execute('SELECT count(*) AS count,max(observed_at) AS latest FROM observations').fetchone()
        stations=c.execute('SELECT count(*) AS count FROM stations').fetchone()['count']
    return {'database':'ready','observation_count':observations['count'],'station_count':stations,'latest_observed_at':observations['latest']}


def nearby_stations(lat,lon,radius_km):
    with connect() as c:
        rows=c.execute('''SELECT s.id,s.vertical_datum,s.metadata AS station_metadata,ST_Y(s.location) AS lat,ST_X(s.location) AS lon,
            src.title AS source,src.url AS source_url,src.license_evidence,
            ST_Distance(s.location::geography,ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography) AS distance_m,
            o.observed_at,o.value,o.unit,o.raw_sha256,o.metadata AS observation_metadata
            FROM stations s JOIN sources src ON src.id=s.source_id
            LEFT JOIN LATERAL (SELECT * FROM observations WHERE station_id=s.id ORDER BY observed_at DESC LIMIT 1) o ON true
            WHERE src.approval_status='approved' AND length(src.license_evidence)>0 AND ST_DWithin(s.location::geography,ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography,%s)
            ORDER BY distance_m LIMIT 30''',(lon,lat,lon,lat,radius_km*1000)).fetchall()
    now=datetime.now(timezone.utc)
    for r in rows:
        r['freshness']='missing' if not r['observed_at'] else ('stale' if (now-r['observed_at']).total_seconds()>3600 else 'recent')
        r['spatial_applicability']='station_only_not_property_water_level'
    return {'results':rows,'stale_after_seconds':3600,'limitations':['ระดับสถานีไม่ใช่ระดับน้ำที่บ้าน และอาจใช้ datum ต่างกัน']}


def observation_series(station_id,start=None,end=None):
    from datetime import timedelta
    with connect() as c:
        station=c.execute("SELECT s.id,s.vertical_datum,s.metadata,src.title AS source,src.url AS source_url FROM stations s JOIN sources src ON src.id=s.source_id WHERE s.id=%s AND src.approval_status='approved' AND length(src.license_evidence)>0",(station_id,)).fetchone()
        if not station:return None
        latest=c.execute('SELECT max(observed_at) AS latest FROM observations WHERE station_id=%s',(station_id,)).fetchone()['latest']
        if end is None:end=latest or datetime.now(timezone.utc)
        if start is None:start=end-timedelta(days=1)
        if start.tzinfo is None or end.tzinfo is None or end<=start or (end-start).total_seconds()>31*86400:raise ValueError('Require timezone-aware interval of at most 31 days')
        rows=c.execute('SELECT observed_at,value,unit,raw_sha256,metadata FROM observations WHERE station_id=%s AND observed_at>=%s AND observed_at<=%s ORDER BY observed_at LIMIT 10001',(station_id,start,end)).fetchall()
        if len(rows)>10000:raise ValueError('Too many observations; shorten interval')
    gaps=[]
    for a,b in zip(rows,rows[1:]):
        delta=(b['observed_at']-a['observed_at']).total_seconds()
        if delta>900:gaps.append({'after':a['observed_at'],'before':b['observed_at'],'seconds':delta})
    return {'station':station,'start':start,'end':end,'results':rows,'count':len(rows),'gaps':gaps,'gap_detection':'gaps >15 minutes; not an official agency completeness rating','interpolation':'none','limitations':['ข้อมูลย้อนหลังในคลัง ไม่ใช่ระดับน้ำที่บ้าน','ช่วงที่ถูกกักกันหรือไม่มีข้อมูลไม่ถูกเติมค่า','เวลา CSV ที่ไม่มี offset แสดงสมมติฐาน timezone ใน metadata']}
