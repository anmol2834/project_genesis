# ============================================================================
# AUTH SERVICE — uses ML base (sentence-transformers + torch)
# ============================================================================
FROM project-genesis-base-ml:latest

WORKDIR /app

# Copy service-specific extra requirements (if any beyond base)
COPY services/auth-service/requirements.txt /tmp/svc-requirements.txt
RUN pip install --no-cache-dir -r /tmp/svc-requirements.txt

# Copy service code last — only this layer rebuilds on code changes
COPY services/auth-service/ /app/services/auth-service/

ENV PYTHONPATH=/app
WORKDIR /app/services/auth-service

EXPOSE 8001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
