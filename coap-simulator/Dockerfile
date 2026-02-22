FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# CoAP default port
EXPOSE 5683/udp

ENTRYPOINT ["python", "server.py"]
