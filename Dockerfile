FROM python:3.15-slim AS runtime
ARG LYCHEE_VERSION=0.24.2
ARG TARGETARCH
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl && rm -rf /var/lib/apt/lists/*
RUN set -eu; case "$TARGETARCH" in arm64) arch=aarch64;; amd64) arch=x86_64;; *) exit 1;; esac; \
    asset="lychee-${arch}-unknown-linux-musl.tar.gz"; \
    curl -fSL "https://github.com/lycheeverse/lychee/releases/download/lychee-v${LYCHEE_VERSION}/${asset}" -o /tmp/lychee.tgz; \
    curl -fSL "https://github.com/lycheeverse/lychee/releases/download/lychee-v${LYCHEE_VERSION}/${asset}.sha256" -o /tmp/lychee.sha256; \
    expected="$(cut -d ' ' -f1 /tmp/lychee.sha256)"; echo "$expected  /tmp/lychee.tgz" | sha256sum -c -; \
    mkdir /tmp/lychee; tar -xzf /tmp/lychee.tgz -C /tmp/lychee; \
    find /tmp/lychee -type f -name lychee -exec cp {} /usr/local/bin/lychee \;; \
    chmod 755 /usr/local/bin/lychee; lychee --version; rm -rf /tmp/lychee*
WORKDIR /app
COPY requirements.lock ./requirements.lock
RUN pip install --no-cache-dir -r requirements.lock
COPY . .
RUN useradd -u 10001 -m audit && mkdir -p /data && chown audit:audit /data
USER audit
ENV PYTHONUNBUFFERED=1 DB_PATH=/data/audit.sqlite3
EXPOSE 8000
CMD ["sh","-c","python manage.py migrate --noinput && python manage.py bootstrap && exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --threads 2 --timeout 120 --no-control-socket --access-logfile -"]
