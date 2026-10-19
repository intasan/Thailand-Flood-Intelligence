"""Offline source-readiness audit. Does not claim to ingest live observations."""
from datetime import datetime
from airflow.decorators import dag, task

@dag(schedule=None, start_date=datetime(2026,1,1), catchup=False, tags=["data-readiness"])
def source_readiness():
    @task
    def audit():
        from pathlib import Path
        import json
        path=Path("/opt/airflow/data/approved_sources.json")
        if not path.exists():
            raise ValueError("No approved source manifest; ingestion remains blocked")
        rows=json.loads(path.read_text())
        if not rows: raise ValueError("Empty source manifest")
        for row in rows:
            for k in ("source_id","license_evidence","vertical_datum","resolution","access_method"):
                if not row.get(k): raise ValueError(f"Missing {k}")
        return {"audited_sources":len(rows),"live_ingestion":False}
    audit()
source_readiness()
