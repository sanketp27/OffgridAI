# syntax=docker/dockerfile:1

# OffGrid AI Backend — Cloud Run service image.
#
# The same image is reused for the catalog-import Cloud Run Job (§10.2):
# override the container command at deploy time with
#   python -m scripts.catalog_import_runner --job-id "$JOB_ID"
# instead of the default `uvicorn` CMD below.

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps: PyMuPDF (pdf skill) and lxml (bs4 parser backend) need a C
# toolchain to build wheels on some base images; kept minimal otherwise.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
# Install dependencies before copying the rest of the source so dependency
# layers are cached across source-only rebuilds.
RUN pip install --no-cache-dir .

COPY . .

# Cloud Run injects $PORT; uvicorn binds to it. Default 8080 for local `docker run`.
ENV PORT=8080
EXPOSE 8080

# Cloud Run services are expected to serve HTTP; Cloud Run Jobs override
# this CMD entirely at deploy/execution time (see module docstring above).
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
