FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=300 \
    PIP_RETRIES=10

WORKDIR /app

COPY services/ai-api/pyproject.toml ./
# Install dependency metadata before copying changing application sources, so
# ordinary code edits reuse this comparatively expensive Docker layer.
RUN --mount=type=cache,target=/root/.cache/pip \
    mkdir -p app \
    && touch app/__init__.py \
    && python -m pip install --upgrade "pip>=26.1.2" \
    && python -m pip install .

COPY services/ai-api/app ./app
COPY services/ai-api/prompts ./prompts
COPY knowledge-base ./knowledge-base
COPY services/ai-api/docker-entrypoint.sh /usr/local/bin/acme-ai-entrypoint

RUN addgroup --system acme \
    && adduser --system --ingroup acme acme \
    && mkdir -p /app/data \
    && chown -R acme:acme /app \
    && chmod 0755 /usr/local/bin/acme-ai-entrypoint

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/acme-ai-entrypoint"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
