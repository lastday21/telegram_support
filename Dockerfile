FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN useradd --create-home appuser

COPY requirements-server.txt .
RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements-server.txt

COPY app ./app

USER appuser

CMD ["python", "-m", "uvicorn", "app.interfaces.http.api:app", "--host", "0.0.0.0", "--port", "8000"]
