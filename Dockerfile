FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy application code first
COPY src/ src/
COPY migrations/ migrations/
COPY alembic.ini .

# Install python dependencies
COPY pyproject.toml .
RUN pip install uv && \
    uv pip install --system --no-cache .

# Create non-root user
RUN useradd -m appuser && chown -R appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "ecoia.main:app", "--host", "0.0.0.0", "--port", "8000"]
