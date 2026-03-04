FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    ENABLE_HOTKEYS=0

WORKDIR /app

RUN useradd --create-home appuser

COPY requirements.txt .
RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY src ./src

USER appuser

CMD ["python", "-m", "src.main"]
