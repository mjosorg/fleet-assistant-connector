ARG BUILD_FROM=ghcr.io/hassio-addons/base:20.0.4

FROM $BUILD_FROM

# Install requirements for add-on
RUN \
  apk add --no-cache \
    wireguard-tools \
    nano \
    jq \
    nftables \
    coreutils \
    python3 \
    py3-pip \
    && pip install --no-cache-dir --break-system-packages requests \
       fastapi \
       uvicorn

COPY rootfs /
