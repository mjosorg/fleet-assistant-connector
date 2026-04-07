# This code will run a webserver to handle a request.

from helper_backup import get_installed_addons
from fastapi import FastAPI, HTTPException
from helper_backup import get_installed_addons
import uvicorn

app = FastAPI(title="Home Assistant Supervisor Proxy")

@app.get("/proxy/addons")
async def fetch_addons():
    """
    Endpoint that triggers the Supervisor API call via the helper method
    and returns the list of installed add-ons.
    """
    try:
        addons = get_installed_addons()
        return {
            "status": "success",
            "count": len(addons),
            "addons": addons
        }
    except EnvironmentError as ee:
        # Specifically catch missing Token errors
        raise HTTPException(status_code=500, detail=str(ee))
    except Exception as e:
        # Catch connection errors or API failures
        raise HTTPException(status_code=502, detail=f"Supervisor API Error: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "online"}
    
uvicorn.run(app, host="0.0.0.0", port=8000)