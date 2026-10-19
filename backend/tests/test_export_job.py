"""Synthetic job-wrapper tests; actual Airflow/HII export is checked in CI."""
import pytest
from app.export_job import run_export_job


def params():
    return {'station':'CPY001','request_id':'TEST_ONLY','start':'2020-01-01T00:00:00Z',
            'end':'2020-01-02T00:00:00Z','interval_seconds':600,'accept_non_commercial':True}


def test_validated_request_calls_fixed_n_flag_and_bounded_directory(tmp_path,monkeypatch):
    calls=[]
    def fake(*args):
        calls.append(args)
        return {'rows':2,'accepted_rows':2,'absent_intervals':142,'simulation_generated':False,'observations_sha256':'a'*64}
    monkeypatch.setattr('app.export_job.export_observations',fake)
    result=run_export_job(params(),tmp_path/'exports')
    assert calls[0][0]=='HII:CPY001' and calls[0][4]==['N']
    assert calls[0][5]==tmp_path/'exports'/'TEST_ONLY'
    assert result['relative_output_directory']=='TEST_ONLY' and result['simulation_generated'] is False


@pytest.mark.parametrize('change',[
    lambda p:p.update(accept_non_commercial=False),
    lambda p:p.update(request_id='../escape'),
    lambda p:p.update(request_id='/absolute'),
    lambda p:p.update(request_id=None),
    lambda p:p.update(station=';echo bad'),
    lambda p:p.update(start=None),
    lambda p:p.update(start='2020-01-01T00:00:00'),
    lambda p:p.update(end='2020-03-01T00:00:00Z'),
    lambda p:p.update(interval_seconds=True),
    lambda p:p.update(interval_seconds=700),
])
def test_invalid_request_rejected_before_query_or_output_creation(tmp_path,monkeypatch,change):
    def fail(*args):raise AssertionError('Database must not be queried')
    monkeypatch.setattr('app.export_job.export_observations',fail)
    p=params();change(p);root=tmp_path/'exports'
    with pytest.raises(ValueError):run_export_job(p,root)
    assert not root.exists()


def test_existing_or_symlink_destination_never_reused(tmp_path,monkeypatch):
    def fail(*args):raise AssertionError('Database must not be queried')
    monkeypatch.setattr('app.export_job.export_observations',fail)
    target=tmp_path/'TEST_ONLY';target.mkdir()
    with pytest.raises(FileExistsError):run_export_job(params(),tmp_path)
    target.rmdir();target.symlink_to(tmp_path/'missing')
    with pytest.raises(FileExistsError):run_export_job(params(),tmp_path)
