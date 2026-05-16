FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    RAN_API_URL=http://metrics-api-service:8000 \
    MODEL_PATH=/app/models/ppo_oran_final.zip \
    STATS_PATH=/app/models/vec_normalize.pkl \
    MPLCONFIGDIR=/tmp/matplotlib

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY requirements-agent.txt .
RUN pip install --no-cache-dir -r requirements-agent.txt

COPY --chown=app:app . .

RUN mkdir -p /app/models && chown app:app /app/models

USER app

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os; open(os.environ.get('MODEL_PATH', '/app/models/ppo_oran_final.zip'))"

CMD ["python", "xapp.py"]