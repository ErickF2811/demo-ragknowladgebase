FROM python:3.10-slim

WORKDIR /app

# Install system dependencies required for building python packages (e.g. psycopg2)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose the application port
EXPOSE 5000

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV API_HOST=0.0.0.0

CMD ["python", "app.py"]
