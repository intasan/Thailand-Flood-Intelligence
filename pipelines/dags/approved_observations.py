"""Only reads operator-approved local inbox files. No fabricated station seed data."""
from datetime import datetime
from airflow.decorators import dag,task

@dag(schedule='@hourly',start_date=datetime(2026,1,1),catchup=False,max_active_runs=1,tags=['observations','approved-local-input'])
def approved_observations():
    @task
    def import_inbox():
        from pathlib import Path
        from app.ingest import ingest
        root=Path('/opt/airflow/data/inbox')
        results=[]
        for csv in sorted(root.glob('*.csv')):
            manifest=csv.with_suffix('.manifest.json')
            if not manifest.is_file():raise ValueError(f'Missing approval manifest for {csv.name}')
            results.append(ingest(csv,manifest))
        return {'files_processed':len(results),'results':results,'note':'empty inbox is not evidence of no flood'}
    import_inbox()
approved_observations()
