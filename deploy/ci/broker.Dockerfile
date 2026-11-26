FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends mosquitto mosquitto-clients && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir '.[dev]' && useradd -m tester
ENV TXORI_CONTRACTS_DIR=/app/contracts/mqtt
USER tester
CMD ["python", "tools/verify_pipeline.py", "--mosquitto", "/usr/sbin/mosquitto", "--passwd", "/usr/bin/mosquitto_passwd"]
