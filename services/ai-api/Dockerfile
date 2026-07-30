FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=300 \
    PIP_RETRIES=10

WORKDIR /app

COPY services/ai-api/pyproject.toml ./
COPY services/ai-api/app ./app
COPY knowledge-base ./knowledge-base
RUN python -m pip install --no-cache-dir --upgrade "pip>=26.1.2" \
    && python -m pip install --no-cache-dir .

RUN addgroup --system acme \
    && adduser --system --ingroup acme acme \
    && chown -R acme:acme /app
USER acme

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
