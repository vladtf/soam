FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies
RUN pip install --no-cache-dir paho-mqtt

# Copy source
COPY . .

# Ensure launcher script is executable
RUN chmod +x /app/run_simulator.sh

# Default to temperature simulator; override via SIMULATOR_TYPE env
ENV SIMULATOR_TYPE=temperature

ENTRYPOINT ["/app/run_simulator.sh"]
