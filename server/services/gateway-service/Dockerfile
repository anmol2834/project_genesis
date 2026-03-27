# ============================================================================
# GATEWAY SERVICE
# ============================================================================
FROM project-genesis-base:latest

WORKDIR /app

COPY services/gateway-service/requirements.txt /tmp/svc-requirements.txt
RUN pip install --no-cache-dir -r /tmp/svc-requirements.txt

COPY services/gateway-service/ /app/services/gateway-service/

ENV PYTHONPATH=/app
WORKDIR /app/services/gateway-service

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
