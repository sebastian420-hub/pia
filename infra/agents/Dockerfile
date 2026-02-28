FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y libpq-dev gcc postgresql-client && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e . 

# Copy source code
COPY src/ src/
COPY .env .env

ENV PYTHONPATH=/app/src

# Default command (can be overridden in docker-compose)
CMD ["python", "src/pia/agents/seismic_agent.py"]
