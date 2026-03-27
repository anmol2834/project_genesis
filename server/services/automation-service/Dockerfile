# ============================================================================
# AUTOMATION SERVICE
# ============================================================================
FROM project-genesis-base:latest

WORKDIR /app

COPY services/automation-service/requirements.txt /tmp/svc-requirements.txt
RUN pip install --no-cache-dir -r /tmp/svc-requirements.txt

COPY services/automation-service/ /app/services/automation-service/

ENV PYTHONPATH=/app
WORKDIR /app/services/automation-service

EXPOSE 8009
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8009"]
