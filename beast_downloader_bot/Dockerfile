# Base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    curl \
    wget \
    gnupg \
    fonts-liberation \
    libmagic1 \
    # Dependencies for matplotlib
    libfreetype6-dev \
    libpng-dev \
    # Clean up
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Create necessary directories
RUN mkdir -p /app/data/downloads /app/data/temp /app/logs

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install additional tools
RUN pip install --no-cache-dir supervisor

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 botuser && \
    chown -R botuser:botuser /app

# Switch to non-root user
USER botuser

# Expose port for webhook (if needed)
EXPOSE 8443

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8443/health')" || exit 1

# Run the bot
CMD ["python", "-m", "src.bot"]