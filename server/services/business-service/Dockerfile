# ============================================================================
# BUSINESS SERVICE
# ============================================================================
FROM project-genesis-base:latest

WORKDIR /app

COPY services/business-service/requirements.txt /tmp/svc-requirements.txt
RUN pip install --no-cache-dir -r /tmp/svc-requirements.txt

COPY services/business-service/ /app/services/business-service/

ENV PYTHONPATH=/app
WORKDIR /app/services/business-service

EXPOSE 8003
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
