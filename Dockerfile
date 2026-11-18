# Ticket Arena: local dashboard, refresh and Google Chat follow-ups in one container.
FROM python:3.12-slim

ARG GH_VERSION=2.62.0
# amd64 (most PCs) or arm64 (Apple Silicon); set by docker build automatically
ARG TARGETARCH=amd64
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl \
 && curl -fsSL "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_${TARGETARCH}.tar.gz" \
    | tar -xz -C /tmp \
 && mv "/tmp/gh_${GH_VERSION}_linux_${TARGETARCH}/bin/gh" /usr/local/bin/gh \
 && rm -rf /tmp/gh_* \
 && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

# The code and data are mounted from this folder at /app, so edits on your PC apply on restart.
WORKDIR /app
ENV TA_BIND=0.0.0.0 \
    TA_AUTO_REFRESH=1 \
    HOME=/tmp \
    PYTHONUNBUFFERED=1
EXPOSE 8765
CMD ["python3", "control.py"]
