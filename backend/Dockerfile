FROM python:3.11-slim

# Prevent Python from writing pyc files to disc & buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy application source code
COPY . .

# Expose server port
EXPOSE 8000

# Healthcheck for AWS container services
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/ || exit 1

# Start app with Gunicorn + Uvicorn workers for production concurrency (supports PORT env var on Render)
CMD ["sh", "-c", "gunicorn -w 4 -k uvicorn.workers.UvicornWorker server:app --bind 0.0.0.0:${PORT:-8000}"]

