FROM python:3.11-slim

WORKDIR /srv

COPY requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r /srv/requirements.txt

COPY app /srv/app

WORKDIR /srv/app

ENV PYTHONUNBUFFERED=1

# Cloud Run يمرّر PORT، لازم نسمع عليه
CMD ["sh", "-c", "python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
