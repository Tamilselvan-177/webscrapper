FROM python:3.11-slim

WORKDIR /app

# Install system dependencies required for Playwright and networking
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    ca-certificates \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    playwright install --with-deps chromium

# Copy the rest of the application code
COPY . .

# Set environment variables for smooth execution & API access
ENV PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright \
    ADZUNA_APP_ID="71b0f298" \
    ADZUNA_APP_KEY="8f2ce8aef294190f8892004471d453d4" \
    REED_API_KEY="01c0076f-09e5-4b02-a6f2-5b3d108a711c"

# Expose backend API port
EXPOSE 8000

# Start the FastAPI application via Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
