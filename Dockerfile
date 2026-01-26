# ---- Base image ----
FROM python:3.11-slim

# ---- Workdir ----
WORKDIR /srv

# ---- Install deps first (better cache) ----
COPY requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r /srv/requirements.txt

# ---- Copy app code ----
COPY app /srv/app

# ---- Cloud Run needs to listen on $PORT ----
ENV PYTHONUNBUFFERED=1

WORKDIR /srv/app

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
