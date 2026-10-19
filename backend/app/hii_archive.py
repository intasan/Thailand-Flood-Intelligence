"""HII monthly archives: real historical observations, never live property flood depth."""
import argparse,csv,hashlib,io,json,math,os,re
from datetime import datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import httpx
from psycopg.types.json import Jsonb

BASE='https://tiservice.hii.or.th/opendata/data_catalog/water_level/'
CATALOG='https://data.go.th/th/dataset/water-level'
LICENSE='Creative Commons Attribution Non-Commercial; version not stated in catalog'
DATUM='HII_MSL_AS_PUBLISHED; EGM2008 transformation unverified'
SOURCE='HII_WATER_LEVEL_ARCHIVE'
MISSING={'','-','null','NULL','-999','9999','999999'}

def sha(raw):return hashlib.sha256(raw).hexdigest()

def station_metadata(raw,code):
    reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
    required={'Station_Code','Station_Name','Latitude','Longitude','Station_Type_Name','Shared_data'}
    if not required.issubset(reader.fieldnames or []):raise ValueError('Unsupported canonical station metadata schema')
    matches=[r for r in reader if r['Station_Code']==code]
    if len(matches)!=1:raise ValueError('Station missing or duplicated in canonical metadata')
    row=matches[0]
    if None in row or row['Station_Type_Name']!='ระดับน้ำ' or row['Shared_data']!='แชร์ข้อมูล':raise ValueError('Station is not a shared water-level station')
    lat,lon=float(row['Latitude']),float(row['Longitude'])
    if not (math.isfinite(lat) and math.isfinite(lon) and -90<=lat<=90 and -180<=lon<=180):raise ValueError('Invalid station coordinate')
    return {'id':'HII:'+code,'lat':lat,'lon':lon,'name':row['Station_Name'],'basin':row.get('Basin_Name'),'province':row.get('Province_Name'),'metadata_sha256':sha(raw),'coordinate_status':'canonical_source_metadata_not_survey_verified'}

def normalize(raw,code,month,source_timezone):
    # CSV contains no offset. Caller chooses a documented assumption, never a hidden UTC conversion.
    tz=ZoneInfo(source_timezone);reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
    if not {'station_code','measure_datetime','water_level','quality_flag'}.issubset(reader.fieldnames or []):raise ValueError('Unsupported water-level CSV schema')
    valid=[];rejected=[];seen=set()
    for line,row in enumerate(reader,2):
        if None in row or row['station_code']!=code:raise ValueError('Unexpected station or column count')
        t=datetime.fromisoformat(row['measure_datetime'])
        if t.tzinfo is not None:raise ValueError('Unexpected timestamp offset; schema review required')
        if t.replace(tzinfo=tz)>datetime.now(timezone.utc):raise ValueError('Historical source contains future timestamp')
        if t.strftime('%Y%m')!=month:raise ValueError('Timestamp outside requested month')
        if t in seen:raise ValueError('Duplicate source timestamp')
        seen.add(t)
        value=row['water_level'].strip();flag=row['quality_flag'].strip()
        reason='missing_value' if value in MISSING else ('not_normal_quality' if flag!='N' else None)
        if reason:rejected.append({'line':line,'reason':reason,'source_quality_flag':flag});continue
        v=float(value)
        if not math.isfinite(v):raise ValueError('Non-finite measurement')
        if v in (-999,9999,999999):rejected.append({'line':line,'reason':'missing_value','source_quality_flag':flag});continue
        valid.append({'station_id':'HII:'+code,'observed_at':t.replace(tzinfo=tz).isoformat(),'value':v,'unit':'m','source_quality_flag':flag,'source_line':line})
    if not seen:raise ValueError('Empty source file')
    return valid,{'source_rows':len(seen),'accepted_rows':len(valid),'quarantined_rows':len(rejected),'quarantine':rejected,'raw_sha256':sha(raw),'source_timezone':source_timezone,'timestamp_status':'assumed_timezone_source_has_no_offset','vertical_datum':DATUM,'data_type':'historical_station_observation','license':LICENSE,'catalog_url':CATALOG}

def bounded_download(url,limit=2_000_000):
    with httpx.Client(timeout=30,follow_redirects=False,headers={'User-Agent':'Thailand-Flood-Intelligence research archive importer (+https://github.com/intasan/Thailand-Flood-Intelligence)'}) as client:
        with client.stream('GET',url) as response:
            response.raise_for_status();chunks=[];size=0
            for chunk in response.iter_bytes():
                size+=len(chunk)
                if size>limit:raise ValueError('Archive file exceeds bounded download size')
                chunks.append(chunk)
            return b''.join(chunks)

def prepare(code,month,destination,source_timezone):
    if not re.fullmatch(r'[A-Z0-9]{2,20}',code):raise ValueError('Invalid station code')
    if not re.fullmatch(r'20\d{2}(0[1-9]|1[0-2])',month):raise ValueError('Invalid YYYYMM')
    root=Path(destination)/month/code;root.mkdir(parents=True,exist_ok=True)
    url=BASE+month[:4]+'/'+month+'/'+code+'.csv'
    meta_path=root/'station_metadata.raw.csv';raw_path=root/'observations.raw.csv'
    # Reuse exact local bytes; explicit deletion is required to fetch revised archives.
    if not meta_path.exists():meta_path.write_bytes(bounded_download(BASE+'0all_stn_metadata.csv'))
    if not raw_path.exists():raw_path.write_bytes(bounded_download(url))
    station=station_metadata(meta_path.read_bytes(),code)
    rows,report=normalize(raw_path.read_bytes(),code,month,source_timezone)
    report.update({'source_url':url,'station':station,'prepared_at':datetime.now(timezone.utc).isoformat()})
    (root/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    return station,rows,report

def import_prepared(station,rows,report):
    import psycopg
    inserted=0
    with psycopg.connect(os.environ['DATABASE_URL']) as c:
        existing=c.execute('SELECT license_evidence,approval_status FROM sources WHERE id=%s',(SOURCE,)).fetchone()
        if existing and existing!=(CATALOG+' | '+LICENSE,'approved'):raise ValueError('Existing source approval differs')
        c.execute("INSERT INTO sources(id,title,url,license_evidence,approval_status) VALUES (%s,%s,%s,%s,'approved') ON CONFLICT DO NOTHING",(SOURCE,'สสน. HII historical water-level archive',CATALOG,CATALOG+' | '+LICENSE))
        existing_station=c.execute('SELECT source_id,vertical_datum,ST_Y(location),ST_X(location) FROM stations WHERE id=%s',(station['id'],)).fetchone()
        if existing_station and existing_station!=(SOURCE,DATUM,station['lat'],station['lon']):raise ValueError('Existing station coordinates/datum differ; operator review required')
        c.execute('INSERT INTO stations(id,source_id,location,vertical_datum,metadata) VALUES (%s,%s,ST_SetSRID(ST_MakePoint(%s,%s),4326),%s,%s) ON CONFLICT DO NOTHING',(station['id'],SOURCE,station['lon'],station['lat'],DATUM,Jsonb(station)))
        for row in rows:
            metadata={'data_type':'historical_station_observation','source_quality_flag':row['source_quality_flag'],'source_line':row['source_line'],'timestamp_status':report['timestamp_status'],'source_timezone':report['source_timezone'],'source_url':report['source_url']}
            existing_value=c.execute('SELECT value,raw_sha256 FROM observations WHERE station_id=%s AND observed_at=%s',(row['station_id'],row['observed_at'])).fetchone()
            if existing_value and existing_value!=(row['value'],report['raw_sha256']):raise ValueError('Conflicting immutable observation; correction workflow required')
            cur=c.execute('INSERT INTO observations(station_id,observed_at,value,unit,raw_sha256,metadata) VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',(row['station_id'],row['observed_at'],row['value'],'m',report['raw_sha256'],Jsonb(metadata)))
            inserted+=cur.rowcount
        c.execute("INSERT INTO ingest_log(source_id,status,raw_sha256,detail) VALUES (%s,'success',%s,%s)",(SOURCE,report['raw_sha256'],json.dumps({'accepted':len(rows),'inserted':inserted,'quarantined':report['quarantined_rows']})))
    return {'inserted_rows':inserted,'accepted_rows':len(rows),'quarantined_rows':report['quarantined_rows']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--station',required=True);p.add_argument('--month',required=True);p.add_argument('--destination',default='/tmp/hii-archive');p.add_argument('--source-timezone',required=True);p.add_argument('--accept-non-commercial',action='store_true');p.add_argument('--import-db',action='store_true');a=p.parse_args()
    if not a.accept_non_commercial:p.error('This source is CC BY-NC. Explicit non-commercial-use acknowledgement required')
    station,rows,report=prepare(a.station,a.month,a.destination,a.source_timezone)
    print(json.dumps({k:v for k,v in report.items() if k!='quarantine'},ensure_ascii=False,indent=2))
    if a.import_db:print(json.dumps(import_prepared(station,rows,report)))
