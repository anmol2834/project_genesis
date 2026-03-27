# ============================================================================
# CAMPAIGN SERVICE
# ============================================================================
FROM project-genesis-base:latest

WORKDIR /app

COPY services/campaign-service/requirements.txt /tmp/svc-requirements.txt
RUN pip install --no-cache-dir -r /tmp/svc-requirements.txt

COPY services/campaign-service/ /app/services/campaign-service/

ENV PYTHONPATH=/app
WORKDIR /app/services/campaign-service

EXPOSE 8006
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8006"]
