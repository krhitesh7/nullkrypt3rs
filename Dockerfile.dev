FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create results directory
RUN mkdir -p results

# Expose port
EXPOSE 8080

# Set environment variables (override these at runtime)
ENV HOST=0.0.0.0
ENV PORT=8080
ENV LLM_MODEL=gemini-2.5-pro
ENV LLM_PROVIDER=gemini

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run the webhook server
CMD ["python", "-u", "httpapi/server.py"]

