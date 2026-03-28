FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Create entrypoint script
RUN echo '#!/bin/bash\n\
python manage.py collectstatic --noinput\n\
python manage.py migrate --noinput\n\
exec daphne -b 0.0.0.0 -p 8000 config.asgi:application' > /app/entrypoint.sh \
    && chmod +x /app/entrypoint.sh

# Expose port
EXPOSE 8000

# Run entrypoint
CMD ["/app/entrypoint.sh"]
