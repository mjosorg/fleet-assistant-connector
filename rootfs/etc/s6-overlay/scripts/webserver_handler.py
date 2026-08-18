import os
import re
import logging
import requests
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import List, Optional
from pydantic import BaseModel, Field
import uvicorn

from helper_backup import (
    create_partial_backup_supervisor,
    get_backup_stream,
    delete_backup_from_supervisor,
    get_installed_addons,
    get_backup_info
)
from helper_updates import (
    get_available_updates,
    update_core,
    update_os,
    update_supervisor,
    update_addon,
)

# Maps the add-on's `log_level` option (bashio's convention) to Python's levels.
_LOG_LEVELS = {
    "trace": logging.DEBUG,
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "notice": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "fatal": logging.CRITICAL,
}
_log_level = _LOG_LEVELS.get(os.environ.get("LOG_LEVEL", "warning").lower(), logging.WARNING)

logging.basicConfig(
    level=_log_level,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Fleet Assistant Supervisor Proxy")

# --- Supervisor resolution-center issue enrichment ---
# The Supervisor's /resolution/info only gives back machine slugs (type, context,
# reference) — no severity or human-readable text. This maps each known issue
# type (see home-assistant/supervisor supervisor/resolution/const.py) to a
# title/description/severity so API consumers don't need Supervisor-specific knowledge.
ISSUE_TYPE_INFO = {
    "app_port_conflict": ("Port conflict", "An add-on's configured port conflicts with another add-on or Home Assistant Core.", "warning"),
    "boot_fail": ("Boot failure", "The system failed to boot correctly.", "critical"),
    "corrupt_docker": ("Corrupt Docker installation", "The Docker installation is corrupt and needs to be repaired.", "critical"),
    "corrupt_repository": ("Corrupt add-on repository", "An add-on repository is corrupt and could not be loaded.", "warning"),
    "corrupt_filesystem": ("Corrupt filesystem", "A filesystem on this system is corrupt.", "critical"),
    "deprecated_app": ("Deprecated add-on", "An installed add-on is deprecated and should be removed or replaced.", "warning"),
    "deprecated_arch_app": ("Unsupported add-on architecture", "An installed add-on no longer supports this system's architecture.", "warning"),
    "detached_app_missing": ("Add-on repository missing", "An installed add-on's repository is no longer available.", "warning"),
    "detached_app_removed": ("Add-on removed from repository", "An installed add-on was removed from its repository.", "warning"),
    "device_access_missing": ("Device access missing", "An add-on is missing access to a required device.", "error"),
    "disabled_data_disk": ("Data disk disabled", "The external data disk is disabled.", "error"),
    "disk_lifetime": ("Disk nearing end of life", "The system disk is reporting it is nearing the end of its lifetime.", "warning"),
    "dns_loop": ("DNS loop detected", "A DNS loop was detected, which can cause connectivity issues.", "warning"),
    "duplicate_os_installation": ("Duplicate OS installation detected", "Another Home Assistant OS installation was detected on this system.", "warning"),
    "dns_server_failed": ("DNS server failed", "The internal DNS server failed to start or is not responding.", "error"),
    "dns_server_ipv6_error": ("DNS server IPv6 error", "The internal DNS server had an IPv6-related error.", "warning"),
    "docker_config": ("Docker configuration issue", "The Docker daemon configuration is not set up as expected.", "warning"),
    "docker_ratelimit": ("Docker Hub rate limit", "Docker Hub's pull rate limit was hit, which can block updates.", "warning"),
    "fatal_error": ("Fatal error", "A fatal error occurred that needs manual attention.", "critical"),
    "free_space": ("Low disk space", "The system is running low on free disk space.", "error"),
    "ipv4_connection_problem": ("IPv4 connectivity problem", "The system cannot reach the internet over IPv4.", "warning"),
    "missing_image": ("Missing container image", "A required container image is missing.", "error"),
    "mount_failed": ("Mount failed", "A configured network/disk mount failed.", "error"),
    "multiple_data_disks": ("Multiple data disks detected", "More than one external data disk was detected.", "warning"),
    "no_current_backup": ("No recent backup", "There is no recent backup of this installation.", "warning"),
    "ntp_sync_failed": ("Time sync failed", "The system clock could not be synchronized over NTP.", "warning"),
    "pwned": ("Compromised add-on/version", "An installed add-on or version was flagged as compromised.", "critical"),
    "reboot_required": ("Restart required", "Home Assistant needs to be restarted for a recent change to take effect.", "warning"),
    "rpi_firmware_update_blocked": ("Raspberry Pi firmware update blocked", "A Raspberry Pi firmware update is blocked.", "warning"),
    "security": ("Security issue", "A security issue was detected on this system.", "critical"),
    "systemd_unit_failed": ("System service failed", "A system service (systemd unit) failed to start.", "error"),
    "update_failed": ("Update failed", "A recent update failed to install.", "error"),
    "update_rollback": ("Update rolled back", "A recent update failed and was automatically rolled back.", "error"),
}

CONTEXT_LABELS = {
    "addon": "Add-on",
    "core": "Core",
    "dns_server": "DNS",
    "mount": "Mount",
    "os": "OS",
    "plugin": "Plugin",
    "supervisor": "Supervisor",
    "store": "Store",
    "system": "System",
}


def _describe_issue(issue: dict) -> dict:
    """Adds a human-readable title/description/severity to a raw Supervisor resolution issue."""
    issue_type = issue.get("type") or ""
    title, description, severity = ISSUE_TYPE_INFO.get(
        issue_type,
        (issue_type.replace("_", " ").capitalize() or "Unknown issue", "No further details are available for this issue type.", "warning"),
    )
    reference = issue.get("reference")
    if reference:
        description = f"{description} ({reference})"
    context = issue.get("context") or ""
    return {
        **issue,
        "title": title,
        "description": description,
        "severity": severity,
        "context_label": CONTEXT_LABELS.get(context, context),
    }


# --- Slug validation ---
SLUG_PATTERN = re.compile(r'^[a-f0-9]{8}$')
ADDON_SLUG_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{1,64}$')

def validate_slug(slug: str) -> str:
    if not SLUG_PATTERN.match(slug):
        raise HTTPException(status_code=400, detail="Invalid backup slug format")
    return slug

def validate_addon_slug(slug: str) -> str:
    if not ADDON_SLUG_PATTERN.match(slug):
        raise HTTPException(status_code=400, detail="Invalid addon slug format")
    return slug

# --- Models ---
class BackupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    addons: List[str]
    folders: Optional[List[str]] = None
    homeassistant: Optional[bool] = True
    homeassistant_exclude_database: Optional[bool] = False
    background: Optional[bool] = False

# --- Routes ---

@app.get("/health")
async def health_check():
    return {"status": "online"}


def _proc_memory() -> tuple:
    """Read memory used/total (MB) from /proc/meminfo."""
    try:
        fields = {}
        with open("/proc/meminfo") as f:
            for line in f:
                key, _, val = line.partition(":")
                fields[key.strip()] = int(val.strip().split()[0])  # kB
        total_mb = fields["MemTotal"] // 1024
        used_mb = (fields["MemTotal"] - fields["MemAvailable"]) // 1024
        return used_mb, total_mb
    except Exception:
        return None, None


def _proc_cpu_percent() -> float | None:
    """Estimate CPU usage (%) from 1-minute load average vs CPU count."""
    try:
        with open("/proc/loadavg") as f:
            load = float(f.read().split()[0])
        cpu_count = os.cpu_count() or 1
        return round(min(load / cpu_count * 100, 100.0), 1)
    except Exception:
        return None


@app.get("/system")
async def system_health():
    """Returns host system metrics: CPU, memory, disk, OS info."""
    from helper_backup import SUPERVISOR_BASE_URL, _auth_headers
    try:
        response = requests.get(
            f"{SUPERVISOR_BASE_URL}/host/info",
            headers=_auth_headers(),
            timeout=10,
        )
        response.raise_for_status()
        d = response.json().get("data", {})
    except requests.HTTPError as e:
        logger.error("Failed to fetch host info from Supervisor: HTTP %s", e.response.status_code)
        raise HTTPException(status_code=502, detail=f"Supervisor API error: {e.response.status_code}")
    except requests.RequestException as e:
        logger.error("Failed to reach Supervisor for host info: %s", e)
        raise HTTPException(status_code=502, detail=f"Supervisor connection error: {str(e)}")

    # cpu_percent and memory fields are optional in the Supervisor API (absent on HAOS 18+)
    # fall back to reading host procfs which is accessible from inside the addon container
    cpu_percent = d.get("cpu_percent")
    memory_used = d.get("memory_used")
    memory_total = d.get("memory_total")

    if cpu_percent is None:
        cpu_percent = _proc_cpu_percent()

    if memory_used is None or memory_total is None:
        memory_used, memory_total = _proc_memory()

    return {
        "cpu_percent": cpu_percent,
        "memory_used": memory_used,
        "memory_total": memory_total,
        "disk_used": d.get("disk_used"),
        "disk_total": d.get("disk_total"),
        "operating_system": d.get("operating_system"),
        "hostname": d.get("hostname"),
        "board": d.get("board"),
    }


@app.get("/apps")
async def fetch_addons():
    """Returns the list of installed Home Assistant add-ons."""
    try:
        apps = get_installed_addons()
        return {
            "status": "success",
            "count": len(apps),
            "apps": apps
        }
    except requests.HTTPError as e:
        logger.error("Failed to fetch add-on list from Supervisor: HTTP %s", e.response.status_code)
        raise HTTPException(status_code=502, detail=f"Supervisor API error: {e.response.status_code}")
    except requests.RequestException as e:
        logger.error("Failed to reach Supervisor for add-on list: %s", e)
        raise HTTPException(status_code=502, detail=f"Supervisor connection error: {str(e)}")
    except EnvironmentError as e:
        logger.error("Cannot fetch add-on list: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/backup/create")
async def create_partial_backup(request: BackupRequest):
    """Triggers a partial backup via the Supervisor."""
    try:
        backup_slug = create_partial_backup_supervisor(
            name=request.name,
            selected_slugs=request.addons,
            folders=request.folders,
            include_ha=request.homeassistant,
            exclude_database=request.homeassistant_exclude_database,
            background=request.background,
        )
        logger.info("Partial backup '%s' created (slug=%s)", request.name, backup_slug)
        return {
            "status": "success",
            "slug": backup_slug,
            "message": f"Partial backup '{request.name}' started"
        }
    except requests.HTTPError as e:
        logger.error("Backup '%s' failed: Supervisor API error %s", request.name, e.response.status_code)
        raise HTTPException(status_code=502, detail=f"Supervisor API error: {e.response.status_code}")
    except requests.RequestException as e:
        logger.error("Backup '%s' failed: Supervisor connection error: %s", request.name, e)
        raise HTTPException(status_code=502, detail=f"Supervisor connection error: {str(e)}")
    except ValueError as e:
        logger.error("Backup '%s' failed: %s", request.name, e)
        raise HTTPException(status_code=502, detail=str(e))
    except EnvironmentError as e:
        logger.error("Backup '%s' failed: %s", request.name, e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/backup/info/{slug}")
async def backup_info_endpoint(slug: str):
    """Returns metadata for a specific backup. Returns 202 if not ready yet."""
    validate_slug(slug)
    try:
        info = get_backup_info(slug)
    except requests.HTTPError as e:
        logger.error("Failed to fetch backup info for '%s': Supervisor API error %s", slug, e.response.status_code)
        raise HTTPException(status_code=502, detail=f"Supervisor API error: {e.response.status_code}")
    except requests.RequestException as e:
        logger.error("Failed to fetch backup info for '%s': %s", slug, e)
        raise HTTPException(status_code=502, detail=f"Supervisor connection error: {str(e)}")
    if not info:
        raise HTTPException(status_code=202, detail="Backup not ready yet, try again shortly")
    return {
        "status": "ready",
        "size": info.get("size"),
        "name": info.get("name")
    }


@app.get("/backup/download/{slug}")
async def download_backup_endpoint(slug: str, background_tasks: BackgroundTasks):
    """Streams a backup file directly from the Supervisor."""
    validate_slug(slug)
    try:
        supervisor_response = get_backup_stream(slug)
        background_tasks.add_task(supervisor_response.close)

        return StreamingResponse(
            supervisor_response.iter_content(chunk_size=8192),
            media_type="application/x-tar",
            headers={
                "Content-Disposition": f"attachment; filename=backup_{slug}.tar",
                "Content-Length": supervisor_response.headers.get("Content-Length", "")
            }
        )
    except requests.HTTPError as e:
        logger.error("Failed to download backup '%s': Supervisor API error %s", slug, e.response.status_code)
        raise HTTPException(status_code=502, detail=f"Supervisor API error: {e.response.status_code}")
    except requests.RequestException as e:
        logger.error("Failed to download backup '%s': %s", slug, e)
        raise HTTPException(status_code=502, detail=f"Supervisor connection error: {str(e)}")


@app.delete("/backup/delete/{slug}")
async def delete_backup_endpoint(slug: str):
    """Permanently deletes a backup from Home Assistant."""
    validate_slug(slug)
    try:
        delete_backup_from_supervisor(slug)
        logger.info("Backup '%s' deleted", slug)
        return {
            "status": "success",
            "slug": slug,
            "message": "Backup successfully removed from storage."
        }
    except requests.HTTPError as e:
        status_code = e.response.status_code
        if status_code == 404:
            raise HTTPException(status_code=404, detail=f"Backup {slug} not found")
        logger.error("Failed to delete backup '%s': Supervisor API error %s", slug, status_code)
        raise HTTPException(status_code=502, detail=f"Supervisor API error: {status_code}")
    except requests.RequestException as e:
        logger.error("Failed to delete backup '%s': %s", slug, e)
        raise HTTPException(status_code=502, detail=f"Supervisor connection error: {str(e)}")


@app.get("/repairs")
async def get_repairs():
    """Returns active repair issues from both HA Core integrations and the Supervisor."""
    from helper_backup import SUPERVISOR_BASE_URL, _auth_headers

    issues = []

    # 1. HA Core integration repairs (authentication expired, YAML errors, etc.)
    try:
        resp = requests.get(
            f"{SUPERVISOR_BASE_URL}/core/api/repairs/issues",
            headers=_auth_headers(),
            timeout=10,
        )
        resp.raise_for_status()
        core_data = resp.json()
        core_list = core_data if isinstance(core_data, list) else core_data.get("issues", [])
        for issue in core_list:
            if issue.get("ignored"):
                continue
            key = (issue.get("translation_key") or "").replace("_", " ").capitalize()
            placeholders = issue.get("translation_placeholders") or {}
            desc = ", ".join(str(v) for v in placeholders.values()) if placeholders else ""
            title = f"{key} — {desc}" if desc else key
            issues.append({
                "title": title or "Unknown issue",
                "domain": issue.get("domain", ""),
                "severity": issue.get("severity", "warning"),
                "source": "core",
            })
    except Exception as e:
        logger.warning("Failed to fetch Core repairs: %s", e)

    # 2. Supervisor resolution issues (disk, docker, boot failures, etc.)
    try:
        resp = requests.get(
            f"{SUPERVISOR_BASE_URL}/resolution/info",
            headers=_auth_headers(),
            timeout=10,
        )
        resp.raise_for_status()
        raw_issues = resp.json().get("data", {}).get("issues", [])
        for issue in raw_issues:
            described = _describe_issue(issue)
            context = described.get("context_label", "Supervisor")
            reference = described.get("reference") or ""
            domain = f"{context}: {reference}" if reference else context
            issues.append({
                "title": described["title"],
                "domain": domain,
                "severity": described["severity"],
                "source": "supervisor",
            })
    except Exception as e:
        logger.warning("Failed to fetch Supervisor resolution issues: %s", e)

    return {"issues": issues}


@app.get("/updates/progress")
async def get_update_progress():
    """Returns numeric install progress (0-100) for any update entity currently installing, or null."""
    from helper_backup import SUPERVISOR_BASE_URL, _auth_headers
    UPDATE_ENTITIES = [
        "update.home_assistant_core_update",
        "update.home_assistant_operating_system_update",
        "update.home_assistant_supervisor_update",
    ]
    for entity_id in UPDATE_ENTITIES:
        try:
            response = requests.get(
                f"{SUPERVISOR_BASE_URL}/core/api/states/{entity_id}",
                headers=_auth_headers(),
                timeout=5,
            )
            if response.status_code != 200:
                continue
            in_progress = response.json().get("attributes", {}).get("in_progress")
            if isinstance(in_progress, (int, float)) and not isinstance(in_progress, bool) and in_progress > 0:
                return {"in_progress": int(in_progress), "entity_id": entity_id}
        except requests.RequestException:
            continue
    return {"in_progress": None}


@app.get("/updates")
async def fetch_available_updates():
    """Returns all available updates: OS, Core, Supervisor, and add-ons."""
    try:
        updates = get_available_updates()
        return {"status": "success", "updates": updates}
    except requests.HTTPError as e:
        logger.error("Failed to fetch available updates: Supervisor API error %s", e.response.status_code)
        raise HTTPException(status_code=502, detail=f"Supervisor API error: {e.response.status_code}")
    except requests.RequestException as e:
        logger.error("Failed to reach Supervisor for available updates: %s", e)
        raise HTTPException(status_code=502, detail=f"Supervisor connection error: {str(e)}")
    except EnvironmentError as e:
        logger.error("Cannot fetch available updates: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


def _run_update(label, fn, *args):
    """Runs an update function and logs any error (used as a BackgroundTask)."""
    try:
        fn(*args)
        logger.info("%s update completed", label)
    except Exception as e:
        logger.error("%s update failed: %s", label, e)


@app.post("/updates/core")
async def trigger_core_update(background_tasks: BackgroundTasks):
    """Triggers a Home Assistant Core update (fire-and-forget)."""
    logger.info("Home Assistant Core update triggered")
    background_tasks.add_task(_run_update, "Home Assistant Core", update_core)
    return {"status": "triggered", "message": "Home Assistant Core update started"}


@app.post("/updates/os")
async def trigger_os_update(background_tasks: BackgroundTasks):
    """Triggers a Home Assistant OS update (fire-and-forget)."""
    logger.info("Home Assistant OS update triggered")
    background_tasks.add_task(_run_update, "Home Assistant OS", update_os)
    return {"status": "triggered", "message": "Home Assistant OS update started"}


@app.post("/updates/supervisor")
async def trigger_supervisor_update(background_tasks: BackgroundTasks):
    """Triggers a Home Assistant Supervisor update (fire-and-forget)."""
    logger.info("Supervisor update triggered")
    background_tasks.add_task(_run_update, "Supervisor", update_supervisor)
    return {"status": "triggered", "message": "Supervisor update started"}


@app.post("/updates/addon/{slug}")
async def trigger_addon_update(slug: str, background_tasks: BackgroundTasks):
    """Triggers an update for a specific add-on by slug (fire-and-forget)."""
    validate_addon_slug(slug)
    logger.info("Add-on '%s' update triggered", slug)
    background_tasks.add_task(_run_update, f"Add-on '{slug}'", update_addon, slug)
    return {"status": "triggered", "message": f"Update started for add-on '{slug}'"}


@app.post("/updates/all")
async def trigger_all_updates(background_tasks: BackgroundTasks):
    """Triggers updates for all available components (fire-and-forget)."""
    try:
        updates = get_available_updates()
    except EnvironmentError as e:
        logger.error("Cannot trigger updates: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    except requests.RequestException as e:
        logger.error("Failed to reach Supervisor for available updates: %s", e)
        raise HTTPException(status_code=502, detail=f"Supervisor connection error: {str(e)}")

    UPDATE_LABELS = {
        "core": "Home Assistant Core",
        "os": "Home Assistant OS",
        "supervisor": "Supervisor",
    }
    UPDATE_HANDLERS = {
        "core": update_core,
        "os": update_os,
        "supervisor": update_supervisor,
    }

    queued = []
    for item in updates:
        update_type = item.get("update_type")
        if update_type in UPDATE_HANDLERS:
            background_tasks.add_task(_run_update, UPDATE_LABELS[update_type], UPDATE_HANDLERS[update_type])
            queued.append(update_type)
        elif update_type == "addon":
            panel_path = item.get("panel_path", "")
            addon_slug = panel_path.rstrip("/").split("/")[-1]
            if ADDON_SLUG_PATTERN.match(addon_slug):
                background_tasks.add_task(_run_update, f"Add-on '{addon_slug}'", update_addon, addon_slug)
                queued.append(addon_slug)

    logger.info("Bulk update triggered: %s", queued if queued else "nothing to update")
    return {"status": "triggered", "queued": queued}


if __name__ == "__main__":
    logger.info("Fleet Assistant Supervisor Proxy listening on port 8321")
    uvicorn.run(app, host="0.0.0.0", port=8321, log_level="warning")