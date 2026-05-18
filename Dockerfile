FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Browsers are pre-installed in this image, but we ensure chromium is ready
RUN playwright install chromium

COPY . .

# Set environment variables
ENV PORT=5000
ENV PYTHONUNBUFFERED=1

EXPOSE 5000

# Use shell form to allow variable expansion for PORT
CMD gunicorn --bind 0.0.0.0:$PORT app:app
