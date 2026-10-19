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
        rows=c.execute('''SELECT s.id,s.vertical_datum,ST_Y(s.location) AS lat,ST_X(s.location) AS lon,
            src.title AS source,src.url AS source_url,src.license_evidence,
            ST_Distance(s.location::geography,ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography) AS distance_m,
            o.observed_at,o.value,o.unit,o.raw_sha256
            FROM stations s JOIN sources src ON src.id=s.source_id
            LEFT JOIN LATERAL (SELECT * FROM observations WHERE station_id=s.id ORDER BY observed_at DESC LIMIT 1) o ON true
            WHERE src.approval_status='approved' AND length(src.license_evidence)>0 AND ST_DWithin(s.location::geography,ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography,%s)
            ORDER BY distance_m LIMIT 30''',(lon,lat,lon,lat,radius_km*1000)).fetchall()
    now=datetime.now(timezone.utc)
    for r in rows:
        r['freshness']='missing' if not r['observed_at'] else ('stale' if (now-r['observed_at']).total_seconds()>3600 else 'recent')
        r['spatial_applicability']='station_only_not_property_water_level'
    return {'results':rows,'stale_after_seconds':3600,'limitations':['ระดับสถานีไม่ใช่ระดับน้ำที่บ้าน และอาจใช้ datum ต่างกัน']}
