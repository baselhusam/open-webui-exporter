FROM python:3.13-slim

# OCI metadata — surfaced on GHCR/Docker Hub and links the image back to source.
LABEL org.opencontainers.image.title="Open WebUI Prometheus Exporter" \
      org.opencontainers.image.description="Prometheus exporter for Open WebUI, polling its REST API (no DB access required)." \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/baselhusam/open-webui-exporter"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY exporter.py metrics.py pricing.py ./
COPY collectors ./collectors

EXPOSE 9090

CMD ["python", "exporter.py"]
