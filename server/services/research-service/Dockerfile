# ============================================================================
# RESEARCH SERVICE
# ============================================================================
FROM project-genesis-base:latest

WORKDIR /app

COPY services/research-service/requirements.txt /tmp/svc-requirements.txt
RUN pip install --no-cache-dir -r /tmp/svc-requirements.txt

COPY services/research-service/ /app/services/research-service/

ENV PYTHONPATH=/app
WORKDIR /app/services/research-service

EXPOSE 8010
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8010"]
