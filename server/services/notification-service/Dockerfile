# ============================================================================
# NOTIFICATION SERVICE
# ============================================================================
FROM project-genesis-base:latest

WORKDIR /app

COPY services/notification-service/requirements.txt /tmp/svc-requirements.txt
RUN pip install --no-cache-dir -r /tmp/svc-requirements.txt

COPY services/notification-service/ /app/services/notification-service/

ENV PYTHONPATH=/app
WORKDIR /app/services/notification-service

EXPOSE 8011
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8011"]
