ARG BUILD_FROM=ghcr.io/hassio-addons/base:19.0.0

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
    && pip install --no-cache-dir --break-system-packages requests

COPY rootfs /
