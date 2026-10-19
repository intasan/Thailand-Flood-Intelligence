import pytest
from app.hii_archive import normalize,station_metadata

META='Station_Code,Station_Name,Latitude,Longitude,Station_Type_Name,Shared_data\nTEST_ONLY,TEST,13,100,ระดับน้ำ,แชร์ข้อมูล\n'.encode()

def test_sentinels_and_unknown_quality_are_quarantined():
    raw=b'station_code,measure_datetime,water_level,quality_flag\nTEST_ONLY,2020-01-01 00:00:00,1.25,N\nTEST_ONLY,2020-01-01 00:10:00,-999,N\nTEST_ONLY,2020-01-01 00:20:00,2,null\n'
    rows,report=normalize(raw,'TEST_ONLY','202001','Asia/Bangkok')
    assert len(rows)==1 and rows[0]['observed_at'].endswith('+07:00')
    assert report['quarantined_rows']==2 and report['timestamp_status']=='assumed_timezone_source_has_no_offset'

def test_duplicate_timestamp_fails_batch():
    raw=b'station_code,measure_datetime,water_level,quality_flag\nTEST_ONLY,2020-01-01 00:00:00,1,N\nTEST_ONLY,2020-01-01 00:00:00,2,N\n'
    with pytest.raises(ValueError):normalize(raw,'TEST_ONLY','202001','Asia/Bangkok')

def test_station_coordinates_and_shared_water_level_required():
    assert station_metadata(META,'TEST_ONLY')['id']=='HII:TEST_ONLY'
    with pytest.raises(ValueError):station_metadata(META.replace('ระดับน้ำ'.encode(),'น้ำฝน'.encode()),'TEST_ONLY')
