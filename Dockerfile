# Use Python 3.9 slim image for smaller size
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY aggregator.py .
COPY config.py .
COPY models.py .
COPY parsers.py .
COPY scheduler.py .

# Create data directory
RUN mkdir -p /app/data

# Set volume for persistent data storage
VOLUME ["/app/data"]

# Default command runs scheduler with 30-minute interval
CMD ["python", "scheduler.py"]
