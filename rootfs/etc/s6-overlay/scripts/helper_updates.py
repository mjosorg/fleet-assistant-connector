import requests
import os

def check_update_available():
    # Get the supervisor token from environment variable

    ##
    ## {"result":"ok","data":{"available_updates":[{"update_type":"core","panel_path":"/update-available/core","version_latest":"2026.1.3"}]}}
    ##

    SUPER_TOKEN = os.environ.get("SUPERVISOR_TOKEN")
    if not SUPER_TOKEN:
        raise EnvironmentError("SUPERVISOR_TOKEN environment variable not set")

    # Define the endpoint
    url = "http://supervisor/available_updates"
    headers = {"Authorization": f"Bearer {SUPER_TOKEN}"}

    try:
        # Sender GET-forespørsel
        response = requests.get(url, headers=headers, timeout=10)
        
        # Sjekker om forespørselen var vellykket (200 OK)
        response.raise_for_status()
        
        data = response.json()
        
        # Eksempel på hvordan man tolker dataen for å matche ditt ønskede format
        if data.get("result") == "ok":
            return {
                "raw_data": data["data"]
            }
            
    except requests.exceptions.HTTPError as err:
        return {"error": f"HTTP error: {err.response.status_code}"}
    except Exception as e:
        return {"error": f"Problem occured: {str(e)}"}


def upload_updates(FleetAssistantServerIP, FleetToken, Installation_id, update_status):
    # Upload to fleet assistant admin server
    url = f"http://{FleetAssistantServerIP}:8000/ha_upload_updates"

    headers = {
        "X-Token": FleetToken
    }
    params = {"installation_id": Installation_id}


    r = requests.post(url, headers=headers, params=params, json=update_status)
        
    if r.status_code == 200:
        return True
    else:
        print(f"Upload of version status failed with status code {r.status_code} and response: {r.json()}")
        return False

