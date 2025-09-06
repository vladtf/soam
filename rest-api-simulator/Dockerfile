FROM python:3.12-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .

# Expose the port
EXPOSE 8002

# Run the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8002", "--log-level", "info"]
