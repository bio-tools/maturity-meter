# syntax=docker/dockerfile:1

# Build wheels separately so compilers and build tools do not enter the runtime image.
FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /build

COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip wheel --wheel-dir /wheels ".[api]"

FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="Maturity meter" \
      org.opencontainers.image.version="0.1.0" \
      org.opencontainers.image.description="Automated maturity model for research software tools" \
    org.opencontainers.image.source="https://github.com/bio-tools/maturity-meter" \
    org.opencontainers.image.url="https://bio-tools.github.io/maturity-meter" \
    org.opencontainers.image.documentation="https://bio-tools.github.io/maturity-meter"
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MATURITY_METER_SERVER_HOST=0.0.0.0 \
    MATURITY_METER_SERVER_PORT=8000

WORKDIR /app

RUN adduser --disabled-password --gecos "" --uid 10001 appuser
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels

USER appuser
EXPOSE 8000
CMD ["maturity-meter-serve"]
