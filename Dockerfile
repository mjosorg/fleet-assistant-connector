ARG BUILD_FROM=ghcr.io/hassio-addons/base:21.0.1

FROM $BUILD_FROM

# Install requirements for add-on
RUN \
  apk add --no-cache \
    wireguard-tools \
    jq \
    nftables \
    coreutils \
    python3 \
    py3-pip \
    && pip install --no-cache-dir --break-system-packages \
       requests~=2.34 \
       fastapi~=0.141 \
       uvicorn~=0.52

COPY rootfs /
