FROM python:3.11-slim AS builder

RUN python -m venv /opt/venv
COPY requirements.txt /tmp/requirements.txt
RUN /opt/venv/bin/python -m pip install --no-cache-dir -r /tmp/requirements.txt

FROM python:3.11-slim AS runtime

RUN groupadd --system agent && useradd --system --gid agent --home-dir /app agent

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY app/ ./app/
COPY utils/ ./utils/

ENV PATH="/opt/venv/bin:${PATH}" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER agent
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=4s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', '8000') + '/health', timeout=2)"]

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"${PORT:-8000}\" --workers 2"]
