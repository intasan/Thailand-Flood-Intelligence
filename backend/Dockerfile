FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libexpat1 libstdc++6 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -c "import rasterio, pyproj, psycopg, cryptography"
COPY app app
RUN mkdir -p /app/cache /app/models /app/archive && chown -R 10001:10001 /app/cache /app/models /app/archive
USER 10001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
