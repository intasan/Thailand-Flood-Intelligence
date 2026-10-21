"""Operator-run, local-file ingestion only. Never downloads unapproved data."""
import csv
import hashlib
import json
import os
from pathlib import Path
from .quality import validate_observation
from .json_input import read_json_object


def load_rows(csv_path, manifest_path):
    raw=Path(csv_path).read_bytes()
    manifest=read_json_object(manifest_path)
    for key in ('source_id','license_evidence','vertical_datum','source_url','approved_by'):
        if not manifest.get(key): raise ValueError(f'Missing {key}')
    if manifest.get('approval_status')!='approved': raise ValueError('Source not approved')
    rows=list(csv.DictReader(raw.decode('utf-8-sig').splitlines()))
    if not rows: raise ValueError('Empty input')
    normalized=[]
    for row in rows:
        # Manifest authority overrides untrusted CSV provenance fields.
        normalized.append(validate_observation({**row,**manifest}))
    return manifest,normalized,hashlib.sha256(raw).hexdigest()


def ingest(csv_path, manifest_path):
    import psycopg
    manifest,rows,digest=load_rows(csv_path,manifest_path)
    # All validation precedes transaction. Any unknown station/datum rolls back the entire batch.
    with psycopg.connect(os.environ['DATABASE_URL']) as conn:
        source=conn.execute('SELECT approval_status,license_evidence FROM sources WHERE id=%s',(manifest['source_id'],)).fetchone()
        if source != ('approved',manifest['license_evidence']): raise ValueError('Source approval does not match database')
        for row in rows:
            station=conn.execute('SELECT source_id,vertical_datum FROM stations WHERE id=%s',(row['station_id'],)).fetchone()
            if station!=(manifest['source_id'],manifest['vertical_datum']): raise ValueError('Unknown station or datum mismatch')
            conn.execute('INSERT INTO observations(station_id,observed_at,value,unit,raw_sha256) VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',
                (row['station_id'],row['observed_at'],float(row['value']),row['unit'],digest))
        conn.execute("INSERT INTO ingest_log(source_id,status,raw_sha256,detail) VALUES (%s,'success',%s,%s)",(manifest['source_id'],digest,f'validated input rows: {len(rows)}'))
    return {'input_rows':len(rows),'raw_sha256':digest}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('csv');p.add_argument('manifest');a=p.parse_args()
    print(json.dumps(ingest(a.csv,a.manifest)))
