FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY sync_netbox_to_itop.py /app/sync_netbox_to_itop.py
COPY mapping.yaml /app/mapping.yaml

USER nobody
CMD ["python", "/app/sync_netbox_to_itop.py", "--daemon", "--mapping", "/app/mapping.yaml"]
