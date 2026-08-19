## 2026.08.00
- Fixed the "defining user bundles in /etc/s6-overlay/s6-rc.d is deprecated" warning by moving the `webserver_proxy` user-bundle membership marker to the new `/etc/s6-overlay/user-bundles.d/user/contents.d/` location.
- Added a `log_level` option (default `warning`) controlling both bashio's own logging and the webserver's — the webserver logged everything at `INFO` unconditionally before this, which is too noisy for normal operation.
- The WireGuard public key is now always logged on startup regardless of `log_level` (it moved to `info` when `log_level` was added, which would have hidden it by default — but it's needed every startup to pair with the server).
- Fixed WireGuard startup failing with "already exists" after an unclean restart, and fixed a regression where filtering `wg-quick`'s command-echo noise broke its own shutdown cleanup (it must stay the exec'd process so its cleanup traps fire).
- Reduced container log noise: `s6-rc` now only logs warnings/errors instead of every service start/stop, and `wg-quick`'s per-command `[#] ...` echo lines are filtered out.
- Enriched `/repairs` output with a human-readable `title`/`description`/`severity` per issue (Supervisor's `/resolution/info` only returns machine slugs), covering all known Supervisor resolution issue types with a safe fallback for unknown ones.
- Startup now checks whether Home Assistant trusts this add-on as a reverse proxy (reading the UI-managed `.storage/http`, or `configuration.yaml` as a fallback) and logs step-by-step setup instructions if it isn't configured.
- Overhauled logging: configured a proper formatter/level for the webserver so `INFO`-level messages are no longer silently dropped, fixed a startup message logged at the wrong severity, and added log lines for backup/update actions and Supervisor communication failures that previously failed silently.
- Pinned `requests`, `fastapi`, and `uvicorn` to compatible-release version ranges in the Dockerfile instead of installing unpinned latest.
- Removed the startup script that wrote `use_x_forwarded_for`/`trusted_proxies` into `configuration.yaml` — Home Assistant has deprecated `http:` YAML configuration in favor of the UI (Settings > System > Network > Reverse proxy). See README for manual setup steps.
- Fixed `/repairs` endpoint: it called `core/api/repairs/issues`, which was never a real Home Assistant REST endpoint (the issue registry is websocket-only). Now reads from the Supervisor's `/resolution/info` endpoint instead.
- Increased backup/update timeouts and treat Supervisor self-restart (connection drop) during a Supervisor update as expected success rather than a failure.
- Added `/system` endpoint returning host CPU, memory, disk, and OS info.
- Added fallback to `/proc/meminfo` and `/proc/loadavg` for CPU/memory reporting on HAOS 18+, where the Supervisor API no longer always returns these fields.
- Added `/repairs` endpoint (later fixed above).

## 2026.05.06
- Added Supervisor API update endpoints: `/updates`, `/updates/core`, `/updates/os`, `/updates/supervisor`, `/updates/addon/{slug}`, `/updates/all`
- Fixed critical bug where `EnvironmentError` caught all `requests` exceptions (timeouts, connection errors) before the intended handler, causing backup failures to return HTTP 500 instead of 502
- Increased backup creation timeout from 60 s to 180 s to handle slow Supervisors
- Fixed `/available_updates` response parsing — updates are nested under `data.available_updates`, not `data` directly
- Fixed addon slug extraction to use `panel_path` instead of non-existent `identifier` field
- Fixed core update type mapping (`"core"` not `"homeassistant"`)

## 2026.01.15
- Improved logging
- Improved loop handling
- Added available updates function

## 2025.10.0
- Added support for uploading backup via API instead of rsync

## 2025.08.0
- Updated build from argument to specify which version is used

## 2025.04.00
- Added webserver for request proxying.

## 2024.10.0
- Added nft package for managing network rules
- Changed wireguard PostUp and PostDown to use nftable instead of legacy iptables command.
