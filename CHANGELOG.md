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
