FROM node:20.11.1-bookworm@sha256:894c91653e564b9ba29400e6e1675bbcbc667158c1706c655dd4ccf84d0f54e8

ENV DEBIAN_FRONTEND=noninteractive \
    NODE_ENV=production

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python-is-python3 \
        tmux \
        asciinema \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m pip install --no-cache-dir --break-system-packages \
    --require-hashes --no-deps -r /tmp/requirements.lock \
    && rm /tmp/requirements.lock

WORKDIR /app

COPY audit-extractor /app/audit-extractor
COPY audit-extractor/data/audit_archive.md /app/data/audit_archive.md
