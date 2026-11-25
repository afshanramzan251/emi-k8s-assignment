FROM python:3.11-slim

# Non-root user banayein
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Dependencies install karein
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code copy karein aur ownership non-root user ko dein
COPY . .
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]