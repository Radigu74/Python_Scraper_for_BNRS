# Base image
FROM python:3.12-slim

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    wget gnupg ca-certificates curl \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libxcomposite1 \
    libxrandr2 libxdamage1 libxss1 libasound2 libxshmfence1 libgbm1 \
    libgtk-3-0 libx11-xcb1 libx11-6 libxcb1 libdrm2 libxext6 \
    libffi-dev libglib2.0-0 libpango-1.0-0 libpangocairo-1.0-0 \
    fonts-liberation libappindicator3-1 lsb-release xvfb \
    && rm -rf /var/lib/apt/lists/*  # Clean up

# Set working directory
WORKDIR /app

# Copy code
COPY . .

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install playwright pandas gspread oauth2client beautifulsoup4

# Install Playwright browser with required dependencies
RUN playwright install --with-deps chromium

# Entrypoint command
CMD ["python", "main.py"]
