import requests
import os
from helper_backup import _get_token

SUPERVISOR_BASE_URL = "http://supervisor"

def check_update_available():
    # Get the supervisor token from environment variable

    ##
    ## {"result":"ok","data":{"available_updates":[{"update_type":"core","panel_path":"/update-available/core","version_latest":"2026.1.3"}]}}
    ##

    token = _get_token()

    url = f"{SUPERVISOR_BASE_URL}/available_updates"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        response.raise_for_status()
        
        data = response.json()

        if data.get("result") == "ok":
            return data["data"]
            
    except requests.exceptions.HTTPError as err:
        return {"error": f"HTTP error: {err.response.status_code}"}
    except Exception as e:
        return {"error": f"Problem occured: {str(e)}"}


def get_fleet_assistant_version():
    """Collecting the current version of the add-on via Supervisor API."""
    
    token = _get_token()

    url = f"{SUPERVISOR_BASE_URL}/addons/self/info"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  
        
        data = response.json()
        
        return data.get("data", {}).get("version")
        
    except requests.exceptions.RequestException as e:
        print(f"Unable to fetch version: {e}")
        return None