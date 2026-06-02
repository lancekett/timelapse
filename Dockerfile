FROM python:3.11-slim

# Install system dependencies (ffmpeg is required for video compilation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set up application directory
WORKDIR /app

# Copy requirements and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code files
COPY ai_analyzer.py archive_compiler.py compiler.py dashboard.py scheduler.py timelapse.py youtube_uploader.py ./

# Create a data directory for persistent files
RUN mkdir -p /data

# Set the working directory to /data so all generated files, configurations, 
# logs, and images are written to the persistent volume mount.
WORKDIR /data

# Expose dashboard port
EXPOSE 8000

# Start both dashboard and capture loop
CMD ["sh", "-c", "python /app/dashboard.py & python /app/timelapse.py"]
