"""Synthetic catchments only, not real drainage divides or model outputs."""
from copy import deepcopy
from hashlib import sha256
import json
import subprocess
import sys
import pytest
from app.river_network import audit_network
from test_river_network import package


def box(x0,y0,x1,y1):
    return [[x0,y0],[x1,y0],[x1,y1],[x0,y1],[x0,y0]]


def catchments():
    p=package(); p['provenance']['catchment_evidence']='SYNTHETIC_TEST_ONLY'
    for row,b in zip(p['reaches'],[(99.99,15,100,15.02),(100,15,100.02,15.02),(99.99,14.98,100.02,15)]):
        row.pop('incremental_catchment_area_m2')
        row['incremental_catchment_geometry']={'type':'Polygon','coordinates':[box(*b)]}
    return p


def test_shared_boundaries_area_accumulation_and_no_mutation():
    p=catchments(); original=deepcopy(p); r=audit_network(p)
    assert p==original
    assert r['catchment_geometry_check']=='non_overlapping_reach_coverage_checked'
    assert r['area_method']=='WGS84_ellipsoidal_from_geometry'
    assert r['hydraulic_validation']=='not_performed'
    rows=r['reaches']
    assert rows[-1]['contributing_area_m2']==pytest.approx(sum(x['incremental_catchment_area_m2'] for x in rows))
    assert all(x['incremental_catchment_area_m2']>0 for x in rows)


def test_holes_orientation_and_multipolygon():
    p=catchments(); coords=p['reaches'][0]['incremental_catchment_geometry']['coordinates']
    before=audit_network(p)['reaches'][0]['incremental_catchment_area_m2']
    coords.append(box(99.991,15.001,99.993,15.003))
    smaller=audit_network(p)['reaches'][0]['incremental_catchment_area_m2']
    assert smaller<before
    for ring in coords: ring.reverse()
    assert audit_network(p)['reaches'][0]['incremental_catchment_area_m2']==pytest.approx(smaller)
    p['reaches'][0]['incremental_catchment_geometry']={'type':'MultiPolygon','coordinates':[coords,[box(99.98,15.001,99.985,15.005)]]}
    assert audit_network(p)['reaches'][0]['incremental_catchment_area_m2']>smaller


def test_overlap_rejected_across_outlets():
    p=catchments();p['reaches'][0]['incremental_catchment_geometry']['coordinates'][0]=box(99.99,15,100.005,15.02)
    p['reaches'][0]['downstream_id']=None
    with pytest.raises(ValueError,match='Overlapping'):audit_network(p)


def test_identical_polygons_rejected():
    p=catchments(); p['reaches'][0]['incremental_catchment_geometry']['coordinates'][0]=box(99.99,15,100.02,15.02)
    p['reaches'][1]['incremental_catchment_geometry']=deepcopy(p['reaches'][0]['incremental_catchment_geometry'])
    with pytest.raises(ValueError,match='Overlapping'):audit_network(p)


@pytest.mark.parametrize('mutation,message',[
    (lambda p:p['reaches'][0].pop('incremental_catchment_geometry'),'every reach'),
    (lambda p:p['provenance'].pop('catchment_evidence'),'catchment_evidence'),
    (lambda p:p['reaches'][0].update(incremental_catchment_geometry=None),'Polygon'),
    (lambda p:p['reaches'][0]['incremental_catchment_geometry']['coordinates'][0].pop(),'closed'),
    (lambda p:p['reaches'][0]['incremental_catchment_geometry']['coordinates'][0][0].append(0),'2D'),
    (lambda p:p['reaches'][0]['incremental_catchment_geometry']['coordinates'][0][0].__setitem__(0,float('nan')),'coordinate'),
    (lambda p:p['reaches'][0]['incremental_catchment_geometry'].update(crs='EPSG:3857'),'WGS84'),
    (lambda p:p['reaches'][0]['incremental_catchment_geometry'].update(coordinates=[box(99,14,99.5,14.5)]),'not covered'),
    (lambda p:p['reaches'][0].update(incremental_catchment_area_m2=1),'declared incremental area'),
    (lambda p:p['reaches'][0]['incremental_catchment_geometry'].update(coordinates=[[[99,15],[100,16],[99,16],[100,15],[99,15]]]),'topology'),
    (lambda p:p['reaches'][0]['incremental_catchment_geometry'].update(coordinates=[box(-179,14,179,16)]),'antimeridian'),
])
def test_bad_geometry_rejected(mutation,message):
    p=catchments();mutation(p)
    with pytest.raises(ValueError,match=message):audit_network(p)


def test_declared_area_agreement_and_geometry_is_used():
    p=catchments(); actual=audit_network(p)['reaches'][0]['incremental_catchment_area_m2']
    p['reaches'][0]['incremental_catchment_area_m2']=actual*1.005
    assert audit_network(p)['reaches'][0]['incremental_catchment_area_m2']==actual
    p['reaches'][0]['incremental_catchment_area_m2']=actual*1.02
    with pytest.raises(ValueError,match='declared'):audit_network(p)


def test_hole_reach_coverage_and_island_catchment():
    p=catchments();p['reaches'][0]['incremental_catchment_geometry']['coordinates'].append(box(99.995,15.005,100.001,15.015))
    with pytest.raises(ValueError):audit_network(p)
    p=catchments();p['reaches'][0]['incremental_catchment_geometry']['coordinates'].append(box(99.991,15.001,99.994,15.005))
    p['reaches'].append({'id':'hole-outlet','downstream_id':None,'geometry':{'type':'LineString','coordinates':[[99.992,15.002],[99.992,15.004]]},'incremental_catchment_geometry':{'type':'Polygon','coordinates':[box(99.991,15.001,99.994,15.005)]}})
    assert audit_network(p)['reach_count']==4


def test_cli_source_integrity_with_geometry(tmp_path):
    source=tmp_path/'raw.bin';source.write_bytes(b'SYNTHETIC_CATCHMENTS_ONLY')
    p=catchments();p['provenance']['raw_sha256']=sha256(source.read_bytes()).hexdigest()
    path=tmp_path/'package.json';path.write_text(json.dumps(p))
    r=subprocess.run([sys.executable,'-m','app.river_network',str(path),'--raw-source',str(source)],capture_output=True,text=True)
    assert r.returncode==0,r.stderr
    result=json.loads(r.stdout)
    assert result['raw_source_checksum']=='matched'
    assert result['catchment_geometry_check']=='non_overlapping_reach_coverage_checked'


def test_candidate_limit(monkeypatch):
    import app.catchments as module
    monkeypatch.setattr(module,'MAX_CANDIDATE_PAIRS',0)
    with pytest.raises(ValueError,match='candidate limit'):audit_network(catchments())
