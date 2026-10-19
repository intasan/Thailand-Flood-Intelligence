FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app app
RUN mkdir -p /app/cache /app/models && chown -R 10001:10001 /app/cache /app/models
USER 10001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
