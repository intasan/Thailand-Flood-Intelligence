"""Manual, bounded non-commercial HII monthly archive import, not a live gauge feed."""
from datetime import datetime
from airflow.decorators import dag,task
from airflow.models.param import Param

@dag(schedule=None,start_date=datetime(2026,1,1),catchup=False,max_active_runs=1,
     params={'station':Param('CPY001',type='string',pattern='^[A-Z0-9]{2,20}$'),
             'month':Param('202609',type='string',pattern='^20[0-9]{2}(0[1-9]|1[0-2])$'),
             'accept_non_commercial':Param(False,type='boolean')},tags=['historical','HII','non-commercial'])
def hii_historical():
    @task
    def import_month(**context):
        from app.hii_archive import prepare,import_prepared
        p=context['params']
        if p['accept_non_commercial'] is not True:raise ValueError('HII source is CC BY-NC; non-commercial-use acknowledgement required')
        station,rows,report=prepare(p['station'],p['month'],'/opt/airflow/hii_archive','Asia/Bangkok')
        return import_prepared(station,rows,report)
    import_month()
hii_historical()
