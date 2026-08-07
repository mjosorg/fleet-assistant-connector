# Home Assistant Add-on: Fleet Assistant Connector

Wireguard client for Home Assistant

## Installation

Follow these steps to get the add-on installed on your system:

1. Navigate in your Home Assistant frontend to **Settings** -> **Add-ons** -> **Add-on Store**.
2. Select **Repositories** from the top right menu.
3. Paste the GitHub URL for the project: https://github.com/mjosorg/fleet-assistant-connector
4. Click on the "ADD" button.
5. The addon is now available at the bottom of the page and can be installed.

## Configuration

Add-on configuration:

```yaml
server:
  host: str
  port: port
  publickey: str
  tunnelip: str
  fleet_assistant_server_ip: str
```

### Option: `server.host` (required)

The public facing hostname or IPv4 address of the Fleet Assistant WireGuard server.

### Option: `server.port` (required)

The port configured on the WireGuard server for WireGuard traffic.

### Option: `server.publickey` (required)

The public key of the WireGuard server (master).

### Option: `server.tunnelip` (required)

The IP address (with CIDR) to assign to this client on the WireGuard tunnel.

### Option: `server.fleet_assistant_server_ip` (required)

The tunnel IP address of the Fleet Assistant server, used as the WireGuard peer's allowed IP.

## Reverse proxy setup

Home Assistant no longer accepts trusted-proxy settings via `configuration.yaml`. See the [README](README.md) for the manual steps to configure this under **Settings > System > Network > Reverse proxy**.
