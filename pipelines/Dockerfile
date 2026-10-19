FROM apache/airflow:2.10.5
RUN pip install --no-cache-dir "psycopg[binary]==3.2.9" "httpx==0.28.1"
COPY backend/app /opt/airflow/flood/app
ENV PYTHONPATH=/opt/airflow/flood
