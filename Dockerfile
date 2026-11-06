ARG BUILD_FROM=ghcr.io/hassio-addons/base:21.0.10

FROM $BUILD_FROM

# Only log warnings/errors for s6 service start/stop — the default (2) logs
# every service starting/stopping on every boot, which is just noise here.
ENV S6_VERBOSITY=1

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
       requests~=2.34.2 \
       fastapi~=0.162.0 \
       uvicorn~=0.54.0 \
       websockets~=17.4

COPY rootfs /
