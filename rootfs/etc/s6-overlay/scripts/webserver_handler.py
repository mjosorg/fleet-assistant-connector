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

# --- Routes ---

@app.get("/health")
async def health_check():
    return {"status": "online"}


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
            include_ha=request.homeassistant
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


@app.post("/updates/core")
async def trigger_core_update():
    """Triggers a Home Assistant Core update."""
    try:
        update_core()
        return {"status": "success", "message": "Home Assistant Core update triggered"}
    except requests.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Supervisor API error: {e.response.status_code}")
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Supervisor connection error: {str(e)}")
    except EnvironmentError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/updates/os")
async def trigger_os_update():
    """Triggers a Home Assistant OS update."""
    try:
        update_os()
        return {"status": "success", "message": "Home Assistant OS update triggered"}
    except requests.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Supervisor API error: {e.response.status_code}")
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Supervisor connection error: {str(e)}")
    except EnvironmentError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/updates/supervisor")
async def trigger_supervisor_update():
    """Triggers a Home Assistant Supervisor update."""
    try:
        update_supervisor()
        return {"status": "success", "message": "Supervisor update triggered"}
    except requests.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Supervisor API error: {e.response.status_code}")
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Supervisor connection error: {str(e)}")
    except EnvironmentError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/updates/addon/{slug}")
async def trigger_addon_update(slug: str):
    """Triggers an update for a specific add-on by slug."""
    validate_addon_slug(slug)
    try:
        update_addon(slug)
        return {"status": "success", "message": f"Update triggered for add-on '{slug}'"}
    except requests.HTTPError as e:
        status_code = e.response.status_code
        if status_code == 404:
            raise HTTPException(status_code=404, detail=f"Add-on '{slug}' not found")
        raise HTTPException(status_code=502, detail=f"Supervisor API error: {status_code}")
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Supervisor connection error: {str(e)}")
    except EnvironmentError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/updates/all")
async def trigger_all_updates():
    """Triggers updates for all available components (OS, Core, Supervisor, add-ons)."""
    try:
        updates = get_available_updates()
    except EnvironmentError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Supervisor connection error: {str(e)}")

    triggered = []
    failed = []

    UPDATE_HANDLERS = {
        "core": ("core", update_core),
        "os": ("os", update_os),
        "supervisor": ("supervisor", update_supervisor),
    }

    for item in updates:
        update_type = item.get("update_type")

        if update_type in UPDATE_HANDLERS:
            label, handler = UPDATE_HANDLERS[update_type]
            try:
                handler()
                triggered.append(label)
            except requests.RequestException as e:
                failed.append({"component": label, "error": str(e)})

        elif update_type == "addon":
            panel_path = item.get("panel_path", "")
            addon_slug = panel_path.rstrip("/").split("/")[-1]
            if not ADDON_SLUG_PATTERN.match(addon_slug):
                failed.append({"component": addon_slug, "error": "Invalid slug in panel_path"})
                continue
            try:
                update_addon(addon_slug)
                triggered.append(addon_slug)
            except requests.RequestException as e:
                failed.append({"component": addon_slug, "error": str(e)})

    return {
        "status": "success" if not failed else "partial",
        "triggered": triggered,
        "failed": failed,
    }


if __name__ == "__main__":
    logger.warning("Webserver proxy starting up")
    uvicorn.run(app, host="0.0.0.0", port=8321, log_level="warning")