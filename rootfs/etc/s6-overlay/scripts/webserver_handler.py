# This code will run a webserver to handle a request.

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import List, Optional
from pydantic import BaseModel
import uvicorn

from helper_backup import create_partial_backup_supervisor, get_backup_stream, delete_backup_from_supervisor, get_installed_addons,get_backup_info

app = FastAPI(title="Fleet assistant Supervisor Proxy")

@app.get("/health")
async def health_check():
    return {"status": "online"}

@app.get("/apps")
async def fetch_addons():
    """
    Endpoint that triggers the Supervisor API call via the helper method
    and returns the list of installed add-ons.
    """
    try:
        apps = get_installed_addons()
        return {
            "status": "success",
            "count": len(apps),
            "apps": apps
        }
    except EnvironmentError as ee:
        # Specifically catch missing Token errors
        raise HTTPException(status_code=500, detail=str(ee))
    except Exception as e:
        # Catch connection errors or API failures
        raise HTTPException(status_code=502, detail=f"Supervisor API Error: {str(e)}")


class BackupRequest(BaseModel):
    name: str
    addons: List[str]
    folders: Optional[List[str]] = ["ssl"]
    homeassistant: Optional[bool] = True

@app.post("/backup/create")
async def create_partial_backup(request: BackupRequest):
    """
    Triggers a partial backup by calling the supervisor helper.
    """
    try:
        # We pass the individual fields directly to the helper.
        # The helper builds the payload and sends the request.
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
        
    except Exception as e:
        # This catches errors from inside the helper (e.g., connection issues or 401s)
        raise HTTPException(status_code=502, detail=f"Backup Partial Error: {str(e)}")

@app.get("/backup/info/{slug}")
async def backup_info_endpoint(slug: str):
    info = get_backup_info(slug)
    if not info:
        raise HTTPException(status_code=404, detail="Backup not found yet")
    return {
        "status": "ready",
        "size": info.get("size"),
        "name": info.get("name")
    }

@app.get("/backup/download/{slug}")
async def download_backup_endpoint(slug: str, background_tasks: BackgroundTasks):
    try:
        # Get the response object from requests
        supervisor_response = get_backup_stream(slug)

        # Define a cleanup task to close the requests response once streaming is done
        background_tasks.add_task(supervisor_response.close)

        return StreamingResponse(
            supervisor_response.iter_content(chunk_size=8192),
            media_type="application/x-tar",
            headers={
                "Content-Disposition": f"attachment; filename=backup_{slug}.tar",
                # Help the client know how much is coming
                "Content-Length": supervisor_response.headers.get("Content-Length", "")
            }
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Download Error: {str(e)}")

@app.delete("/backup/delete/{slug}")
async def delete_backup_endpoint(slug: str):
    """
    Endpoint to permanently delete a backup from the Home Assistant system.
    """
    try:
        # Trigger the supervisor deletion logic
        delete_backup_from_supervisor(slug)
        
        return {
            "status": "success",
            "slug": slug,
            "message": "Backup successfully removed from storage."
        }
        
    except Exception as e:
        # If the slug doesn't exist, Supervisor returns a 404, 
        # which will be caught and reported here.
        raise HTTPException(status_code=502, detail=f"Delete Error: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8321, log_level="warning")