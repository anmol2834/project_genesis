# ============================================================================
# ANALYTICS SERVICE
# ============================================================================
FROM project-genesis-base:latest

WORKDIR /app

COPY services/analytics-service/requirements.txt /tmp/svc-requirements.txt
RUN pip install --no-cache-dir -r /tmp/svc-requirements.txt

COPY services/analytics-service/ /app/services/analytics-service/

ENV PYTHONPATH=/app
WORKDIR /app/services/analytics-service

EXPOSE 8008
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8008"]
