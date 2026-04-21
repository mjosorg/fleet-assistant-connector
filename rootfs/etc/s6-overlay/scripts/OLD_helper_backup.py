    # This is an example code for testing ha backup upload endpoint. 
import hashlib
import requests
import os 

def _get_token() -> str:
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        raise EnvironmentError("SUPERVISOR_TOKEN environment variable not set")
    return token

def create_partial_backup_supervisor(name, selected_slugs, folders=["ssl"], include_ha=True):
    """
    Triggers a partial backup via the Home Assistant Supervisor API.
    """
    # 1. Get the supervisor token
    SUPER_TOKEN = _get_token()

    # 2. Define the Supervisor endpoint for partial backups
    url = "http://supervisor/backups/new/partial"
    headers = {
        "Authorization": f"Bearer {SUPER_TOKEN}",
        "Content-Type": "application/json"
    }

    # 3. Construct the payload
    payload = {
        "name": name,
        "addons": selected_slugs,
        "homeassistant": include_ha,
        "folders": folders
    }

    # 4. Send POST request
    # Partial backups can take a moment to initialize; 60s timeout is safe.
    response = requests.post(url, headers=headers, json=payload, timeout=60)

    # 5. Check for errors
    if not response.ok:
        raise Exception(f"Partial backup failed: {response.status_code} {response.text}")

    # 6. Parse and return the slug
    data = response.json()
    backup_slug = data.get("data", {}).get("slug")

    if not backup_slug:
        raise ValueError("Supervisor API did not return a backup slug")

    return backup_slug

def get_backup_stream(backup_slug):
    token = _get_token()

    url = f"http://supervisor/backups/{backup_slug}/download"
    headers = {"Authorization": f"Bearer {token}"}

    # IMPORTANT: We do not use a 'with' block here because 
    # we need the connection to stay open for FastAPI to stream it.
    response = requests.get(url, headers=headers, stream=True, timeout=None)
    
    if not response.ok:
        raise Exception(f"Supervisor download failed: {response.status_code}")
        
    return response
    
def get_backup_info(backup_slug):
    """Queries the Supervisor directly for backup metadata."""
    token = _get_token()

    url = f"http://supervisor/backups/{backup_slug}/info"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.ok:
            return response.json().get("data")
    except Exception:
        return None
    return None

def delete_backup_from_supervisor(backup_slug):
    """
    Communicates with the Supervisor to delete a specific backup file.
    """
    SUPER_TOKEN = _get_token()

    # The Supervisor API endpoint for deletion
    url = f"http://supervisor/backups/{backup_slug}"
    headers = {"Authorization": f"Bearer {SUPER_TOKEN}"}

    # Execute the deletion
    response = requests.delete(url, headers=headers, timeout=20)

    if not response.ok:
        raise Exception(f"Supervisor failed to delete {backup_slug}: {response.text}")
    
    return True

        
def get_installed_addons():
    """
    Fetches the list of installed add-ons from the Home Assistant Supervisor API.
    """
    # Get the supervisor token from environment variable
    SUPER_TOKEN = _get_token()

    # Define the endpoint for add-ons
    url = "http://supervisor/addons"
    headers = {
        "Authorization": f"Bearer {SUPER_TOKEN}",
        "Content-Type": "application/json"
    }

    # Send GET request to fetch add-on data
    response = requests.get(url, headers=headers, timeout=30)

    # Check for errors
    if not response.ok:
        raise Exception(f"Failed to fetch add-ons: {response.status_code} {response.text}")

    # Parse JSON response
    data = response.json()
    
    # The API returns the list under data -> addons
    # Since we are calling /addons, everything in this list is an installed addon.
    installed_addons = data.get("data", {}).get("addons", [])

    return installed_addons