# ============================================================================
# USER SERVICE
# ============================================================================
FROM project-genesis-base:latest

WORKDIR /app

COPY services/user-service/requirements.txt /tmp/svc-requirements.txt
RUN pip install --no-cache-dir -r /tmp/svc-requirements.txt

COPY services/user-service/ /app/services/user-service/

ENV PYTHONPATH=/app
WORKDIR /app/services/user-service

EXPOSE 8002
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
