"""Manual, explicit-window research export; no source download or public writes."""
from datetime import datetime
from airflow.decorators import dag,task
from airflow.models.param import Param


@dag(schedule=None,start_date=datetime(2026,1,1),catchup=False,max_active_runs=1,
     params={'station':Param('CPY001',type='string',pattern='^[A-Z0-9]{2,20}$'),
             'request_id':Param(None,type=['null','string'],pattern='^[A-Za-z0-9_-]{1,64}$'),
             'start':Param(None,type=['null','string']),
             'end':Param(None,type=['null','string']),
             'interval_seconds':Param(600,type='integer',minimum=60,maximum=86400),
             'accept_non_commercial':Param(False,type='boolean')},
     tags=['historical','HII','research-export','non-commercial'])
def hii_observation_export():
    @task(retries=0)
    def export_snapshot(**context):
        import logging
        from app.export_job import run_export_job
        result=run_export_job(context['params'],'/opt/airflow/research_exports')
        logging.info('Historical HII export: request=%s station=%s rows=%s accepted=%s absent=%s csv_sha256=%s simulation_generated=%s',
            result['request_id'],result['station_id'],result['rows'],result['accepted_rows'],
            result['absent_intervals'],result['observations_sha256'],result['simulation_generated'])
        # XCom contains only the small receipt, never the observation records.
        return result
    export_snapshot()


hii_observation_export()
