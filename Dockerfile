ARG BUILD_FROM=ghcr.io/hassio-addons/base:18.2.1

FROM $BUILD_FROM

# Install requirements for add-on
RUN \
  apk add --no-cache \
    wireguard-tools \
    openssh \
    rsync \
    nano \
    jq \
    nftables \
    coreutils \
    python3

COPY rootfs /
