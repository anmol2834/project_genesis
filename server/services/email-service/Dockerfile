# ============================================================================
# EMAIL SERVICE
# ============================================================================
FROM project-genesis-base:latest

WORKDIR /app

COPY services/email-service/requirements.txt /tmp/svc-requirements.txt
RUN pip install --no-cache-dir -r /tmp/svc-requirements.txt

COPY services/email-service/ /app/services/email-service/

ENV PYTHONPATH=/app
WORKDIR /app/services/email-service

EXPOSE 8004
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8004"]
