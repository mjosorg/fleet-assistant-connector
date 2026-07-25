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

logger = logging.getLogger(__name__)

app = FastAPI(title="Fleet Assistant Supervisor Proxy")

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


@app.get("/system")
async def system_health():
    """Returns host system metrics: CPU, memory, disk, OS info from the Supervisor."""
    from helper_backup import SUPERVISOR_BASE_URL, _auth_headers
    try:
        response = requests.get(
            f"{SUPERVISOR_BASE_URL}/host/info",
            headers=_auth_headers(),
            timeout=10,
        )
        response.raise_for_status()
        d = response.json().get("data", {})
        return {
            "cpu_percent": d.get("cpu_percent"),
            "memory_used": d.get("memory_used"),
            "memory_total": d.get("memory_total"),
            "disk_used": d.get("disk_used"),
            "disk_total": d.get("disk_total"),
            "operating_system": d.get("operating_system"),
            "hostname": d.get("hostname"),
            "board": d.get("board"),
        }
    except requests.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Supervisor API error: {e.response.status_code}")
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Supervisor connection error: {str(e)}")


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
        raise HTTPException(status_code=502, detail=f"Supervisor API error: {e.response.status_code}")
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Supervisor connection error: {str(e)}")
    except EnvironmentError as e:
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
        return {
            "status": "success",
            "slug": backup_slug,
            "message": f"Partial backup '{request.name}' started"
        }
    except requests.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Supervisor API error: {e.response.status_code}")
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Supervisor connection error: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except EnvironmentError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/backup/info/{slug}")
async def backup_info_endpoint(slug: str):
    """Returns metadata for a specific backup. Returns 202 if not ready yet."""
    validate_slug(slug)
    try:
        info = get_backup_info(slug)
    except requests.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Supervisor API error: {e.response.status_code}")
    except requests.RequestException as e:
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
        raise HTTPException(status_code=502, detail=f"Supervisor API error: {e.response.status_code}")
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Supervisor connection error: {str(e)}")


@app.delete("/backup/delete/{slug}")
async def delete_backup_endpoint(slug: str):
    """Permanently deletes a backup from Home Assistant."""
    validate_slug(slug)
    try:
        delete_backup_from_supervisor(slug)
        return {
            "status": "success",
            "slug": slug,
            "message": "Backup successfully removed from storage."
        }
    except requests.HTTPError as e:
        status_code = e.response.status_code
        if status_code == 404:
            raise HTTPException(status_code=404, detail=f"Backup {slug} not found")
        raise HTTPException(status_code=502, detail=f"Supervisor API error: {status_code}")
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Supervisor connection error: {str(e)}")


@app.get("/repairs")
async def get_repairs():
    """Returns all active repair issues from the Home Assistant Core API."""
    from helper_backup import SUPERVISOR_BASE_URL, _auth_headers
    try:
        response = requests.get(
            f"{SUPERVISOR_BASE_URL}/core/api/repairs/issues",
            headers=_auth_headers(),
            timeout=10,
        )
        response.raise_for_status()
        return {"issues": response.json().get("issues", [])}
    except requests.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Supervisor API error: {e.response.status_code}")
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Supervisor connection error: {str(e)}")


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
        raise HTTPException(status_code=502, detail=f"Supervisor API error: {e.response.status_code}")
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Supervisor connection error: {str(e)}")
    except EnvironmentError as e:
        raise HTTPException(status_code=500, detail=str(e))


def _run_update(fn, *args):
    """Runs an update function and logs any error (used as a BackgroundTask)."""
    try:
        fn(*args)
    except Exception as e:
        logger.error("Background update failed (%s %s): %s", fn.__name__, args, e)


@app.post("/updates/core")
async def trigger_core_update(background_tasks: BackgroundTasks):
    """Triggers a Home Assistant Core update (fire-and-forget)."""
    background_tasks.add_task(_run_update, update_core)
    return {"status": "triggered", "message": "Home Assistant Core update started"}


@app.post("/updates/os")
async def trigger_os_update(background_tasks: BackgroundTasks):
    """Triggers a Home Assistant OS update (fire-and-forget)."""
    background_tasks.add_task(_run_update, update_os)
    return {"status": "triggered", "message": "Home Assistant OS update started"}


@app.post("/updates/supervisor")
async def trigger_supervisor_update(background_tasks: BackgroundTasks):
    """Triggers a Home Assistant Supervisor update (fire-and-forget)."""
    background_tasks.add_task(_run_update, update_supervisor)
    return {"status": "triggered", "message": "Supervisor update started"}


@app.post("/updates/addon/{slug}")
async def trigger_addon_update(slug: str, background_tasks: BackgroundTasks):
    """Triggers an update for a specific add-on by slug (fire-and-forget)."""
    validate_addon_slug(slug)
    background_tasks.add_task(_run_update, update_addon, slug)
    return {"status": "triggered", "message": f"Update started for add-on '{slug}'"}


@app.post("/updates/all")
async def trigger_all_updates(background_tasks: BackgroundTasks):
    """Triggers updates for all available components (fire-and-forget)."""
    try:
        updates = get_available_updates()
    except EnvironmentError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Supervisor connection error: {str(e)}")

    UPDATE_HANDLERS = {
        "core": update_core,
        "os": update_os,
        "supervisor": update_supervisor,
    }

    queued = []
    for item in updates:
        update_type = item.get("update_type")
        if update_type in UPDATE_HANDLERS:
            background_tasks.add_task(_run_update, UPDATE_HANDLERS[update_type])
            queued.append(update_type)
        elif update_type == "addon":
            panel_path = item.get("panel_path", "")
            addon_slug = panel_path.rstrip("/").split("/")[-1]
            if ADDON_SLUG_PATTERN.match(addon_slug):
                background_tasks.add_task(_run_update, update_addon, addon_slug)
                queued.append(addon_slug)

    return {"status": "triggered", "queued": queued}


if __name__ == "__main__":
    logger.warning("Webserver proxy starting up")
    uvicorn.run(app, host="0.0.0.0", port=8321, log_level="warning")