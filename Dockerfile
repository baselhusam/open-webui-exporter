FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY exporter.py metrics.py pricing.py ./
COPY collectors ./collectors

EXPOSE 9090

CMD ["python", "exporter.py"]
