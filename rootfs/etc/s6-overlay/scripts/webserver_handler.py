import re
import logging
import requests
from fastapi import FastAPI, HTTPException, BackgroundTasks, status
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

logger = logging.getLogger(__name__)

app = FastAPI(title="Fleet Assistant Supervisor Proxy")
logger.warning("Webserver proxy starting up")

# --- Slug validation ---
SLUG_PATTERN = re.compile(r'^[a-f0-9]{8}$')

def validate_slug(slug: str) -> str:
    """Ensures the slug is a valid 8-char hex string before passing to Supervisor."""
    if not SLUG_PATTERN.match(slug):
        raise HTTPException(status_code=400, detail="Invalid backup slug format")
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
    except EnvironmentError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except requests.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Supervisor API error: {e.response.status_code}")
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Supervisor connection error: {str(e)}")


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
    except EnvironmentError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except requests.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Supervisor API error: {e.response.status_code}")
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Supervisor connection error: {str(e)}")


@app.get("/backup/info/{slug}")
async def backup_info_endpoint(slug: str):
    """Returns metadata for a specific backup. Returns 202 if not ready yet."""
    validate_slug(slug)
    info = get_backup_info(slug)
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


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8321, log_level="warning")
