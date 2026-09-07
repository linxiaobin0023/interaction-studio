FROM node:24-alpine@sha256:e67514e5d0f6c46656005e1b693b2ec9d52e80b641307de684d4a015ba7a4eaf AS web
WORKDIR /web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY apps/web ./
RUN npm run build

FROM python:3.12-slim@sha256:94c48f067d4a3e6b78f543821e5c520875571886ef9180bb429354c274276baa

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    WEB_DIST_ROOT=/app/web

WORKDIR /app

COPY apps/api/pyproject.toml apps/api/constraints.lock ./apps/api/
# Keep dependency installation cached when only application source changes.
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('apps/api/pyproject.toml', 'rb'))['project']['dependencies']))" > /tmp/runtime-requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -c apps/api/constraints.lock -r /tmp/runtime-requirements.txt

COPY alembic.ini ./
COPY apps/api/migrations ./apps/api/migrations
COPY apps/api/src ./apps/api/src
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-deps -c apps/api/constraints.lock apps/api
COPY --from=web /web/dist /app/web

USER 65532:65532
EXPOSE 8000
CMD ["uvicorn", "interaction_studio_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
