FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY models.py .
COPY client.py .
COPY server/ server/

# Expose port (match project default 8000)
EXPOSE 7860

# Run the server
# Use a single worker to avoid WebSocket handshake problems with multiprocessing.
EXPOSE 8000
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"]