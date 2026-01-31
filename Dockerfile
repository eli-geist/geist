FROM python:3.12-slim

WORKDIR /app

# System dependencies (inkl. SSH und curl für volle Autonomie)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    openssh-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY eli/ eli/

# Run as non-root
RUN useradd -m eli && \
    mkdir -p /app/data && \
    chown -R eli:eli /app
USER eli

# Default: run the Telegram bot
CMD ["python", "-m", "eli.main"]
