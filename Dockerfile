FROM python:3.11-slim

WORKDIR /srv

# Install deps first (better cache)
COPY requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r /srv/requirements.txt

# Copy app code
COPY app /srv/app

ENV PYTHONUNBUFFERED=1

# Cloud Run expects 8080
CMD ["python","-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8080"]
