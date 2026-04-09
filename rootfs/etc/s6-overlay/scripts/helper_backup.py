import requests
import os
from typing import Optional

def create_partial_backup_supervisor(name, selected_slugs, folders=["ssl"], include_ha=True):
    """
    Triggers a partial backup via the Home Assistant Supervisor API.
    """
    # 1. Get the supervisor token
    SUPER_TOKEN = os.environ.get("SUPERVISOR_TOKEN")
    if not SUPER_TOKEN:
        raise EnvironmentError("SUPERVISOR_TOKEN environment variable not set")

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
    token = os.environ.get("SUPERVISOR_TOKEN")
    url = f"http://supervisor/backups/{backup_slug}/download"
    headers = {"Authorization": f"Bearer {token}"}

    # IMPORTANT: We do not use a 'with' block here because 
    # we need the connection to stay open for FastAPI to stream it.
    response = requests.get(url, headers=headers, stream=True, timeout=None)
    
    if not response.ok:
        raise Exception(f"Supervisor download failed: {response.status_code}")
        
    return response

def delete_backup_from_supervisor(backup_slug):
    """
    Communicates with the Supervisor to delete a specific backup file.
    """
    SUPER_TOKEN = os.environ.get("SUPERVISOR_TOKEN")
    if not SUPER_TOKEN:
        raise EnvironmentError("SUPERVISOR_TOKEN environment variable not set")

    # The Supervisor API endpoint for deletion
    url = f"http://supervisor/backups/{backup_slug}"
    headers = {"Authorization": f"Bearer {SUPER_TOKEN}"}

    # Execute the deletion
    response = requests.delete(url, headers=headers, timeout=20)

    if not response.ok:
        raise Exception(f"Supervisor failed to delete {backup_slug}: {response.text}")
    
    return True

def create_backup():
    # Get the supervisor token from environment variable
    SUPER_TOKEN = os.environ.get("SUPERVISOR_TOKEN")
    if not SUPER_TOKEN:
        raise EnvironmentError("SUPERVISOR_TOKEN environment variable not set")
    return token

def _auth_headers(content_type: bool = False) -> dict:
    """Build standard auth headers, optionally with Content-Type."""
    headers = {"Authorization": f"Bearer {_get_token()}"}
    if content_type:
        headers["Content-Type"] = "application/json"
    return headers

def create_partial_backup_supervisor(
    name: str,
    selected_slugs: list,
    folders: Optional[list] = None,
    include_ha: bool = True
) -> str:
    """Triggers a partial backup via the Home Assistant Supervisor API."""
    if folders is None:
        folders = ["ssl"]  # Avoid mutable default argument

    payload = {
        "name": name,
        "addons": selected_slugs,
        "homeassistant": include_ha,
        "folders": folders
    }

    response = requests.post(
        f"{SUPERVISOR_BASE_URL}/backups/new/partial",
        headers=_auth_headers(content_type=True),
        json=payload,
        timeout=60
    )
    response.raise_for_status()  # Raises HTTPError with status code automatically

    backup_slug = response.json().get("data", {}).get("slug")
    if not backup_slug:
        raise ValueError("Supervisor API did not return a backup slug")

    return backup_slug

def get_backup_stream(backup_slug: str):
    """
    Returns an open streaming response for the given backup.
    IMPORTANT: Caller is responsible for closing the response when done.
    """
    response = requests.get(
        f"{SUPERVISOR_BASE_URL}/backups/{backup_slug}/download",
        headers=_auth_headers(),
        stream=True,
        timeout=None
    )
    response.raise_for_status()
    return response

def get_backup_info(backup_slug: str) -> Optional[dict]:
    """Queries the Supervisor directly for backup metadata. Returns None if not found."""
    try:
        response = requests.get(
            f"{SUPERVISOR_BASE_URL}/backups/{backup_slug}/info",
            headers=_auth_headers(),
            timeout=10
        )
        response.raise_for_status()
        return response.json().get("data")
    except requests.HTTPError:
        return None  # Backup not found or not ready
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to fetch backup info for {backup_slug}: {e}") from e

def delete_backup_from_supervisor(backup_slug: str) -> bool:
    """Permanently deletes a backup from Home Assistant."""
    response = requests.delete(
        f"{SUPERVISOR_BASE_URL}/backups/{backup_slug}",
        headers=_auth_headers(),
        timeout=20
    )
    response.raise_for_status()
    return True

def get_installed_addons() -> list:
    """Fetches the list of installed add-ons from the Home Assistant Supervisor API."""
    response = requests.get(
        f"{SUPERVISOR_BASE_URL}/addons",
        headers=_auth_headers(),
        timeout=30
    )
    response.raise_for_status()
    return response.json().get("data", {}).get("addons", [])