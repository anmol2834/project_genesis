# ============================================================================
# LEADS SERVICE
# ============================================================================
FROM project-genesis-base:latest

WORKDIR /app

COPY services/leads-service/requirements.txt /tmp/svc-requirements.txt
RUN pip install --no-cache-dir -r /tmp/svc-requirements.txt

COPY services/leads-service/ /app/services/leads-service/

ENV PYTHONPATH=/app
WORKDIR /app/services/leads-service

EXPOSE 8007
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8007"]
