FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=300 \
    PIP_RETRIES=10

WORKDIR /app

COPY pyproject.toml ./
# Keep dependency installation independent from changing application sources.
RUN --mount=type=cache,target=/root/.cache/pip \
    mkdir -p app \
    && touch app/__init__.py \
    && python -m pip install --upgrade "pip>=26.1.2" \
    && python -m pip install .

COPY app ./app

RUN addgroup --system acme \
    && adduser --system --ingroup acme acme \
    && mkdir -p /app/data \
    && chown -R acme:acme /app

COPY docker-entrypoint.sh /usr/local/bin/acme-entrypoint
RUN chmod 0755 /usr/local/bin/acme-entrypoint

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/acme-entrypoint"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
