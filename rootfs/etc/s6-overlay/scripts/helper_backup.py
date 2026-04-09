    # This is an example code for testing ha backup upload endpoint. 
import hashlib
import requests
import os 

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
    """
    Requests the backup stream from Supervisor but does not save it to disk.
    """
    SUPER_TOKEN = os.environ.get("SUPERVISOR_TOKEN")
    if not SUPER_TOKEN:
        raise EnvironmentError("SUPERVISOR_TOKEN environment variable not set")

    url = f"http://supervisor/backups/{backup_slug}/download"
    headers = {"Authorization": f"Bearer {SUPER_TOKEN}"}

    # We return the response object itself to be used in a StreamingResponse
    response = requests.get(url, headers=headers, stream=True)
    
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

    # Define the endpoint
    url = "http://supervisor/backups/new/full"
    headers = {"Authorization": f"Bearer {SUPER_TOKEN}"}

    # Send POST request to create a full backup
    response = requests.post(url, headers=headers)

    # Check for errors
    if not response.ok:
        raise Exception(f"Backup creation failed: {response.status_code} {response.text}")

    # Parse JSON response
    data = response.json()
    backup_slug = data.get("data", {}).get("slug")

    if not backup_slug:
        raise ValueError("No backup slug returned in response")

    return backup_slug

def download_backup(backup_slug, file_name):
    # Get the supervisor token from environment variable
    SUPER_TOKEN = os.environ.get("SUPERVISOR_TOKEN")
    if not SUPER_TOKEN:
        raise EnvironmentError("SUPERVISOR_TOKEN environment variable not set")

    # Construct the download URL
    url = f"http://supervisor/backups/{backup_slug}/download"
    headers = {"Authorization": f"Bearer {SUPER_TOKEN}"}

    # Stream the download to a file
    with requests.get(url, headers=headers, stream=True) as response:
        if not response.ok:
            raise Exception(f"Download failed: {response.status_code} {response.text}")

        with open(file_name, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:  # filter out keep-alive chunks
                    f.write(chunk)


def upload_backup(FleetAssistantServerIP, FleetToken, Installation_id, filename):
    # Upload to fleet assistant admin server
    url = f"http://{FleetAssistantServerIP}:8000/ha_upload_backup"


    # Calculate hash before sending
    sha256 = hashlib.sha256()
    with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    expected_hash = sha256.hexdigest()

    headers = {
        "X-Filename": os.path.basename(filename),
        "X-Checksum-Sha256": expected_hash,
        "X-Token": FleetToken
    }
    params = {"installation_id": Installation_id}

    with open(filename, "rb") as f:
        r = requests.post(url, data=f, headers=headers, params=params)
        
    if r.status_code == 200:
        return True
    else:
        print(f"Upload failed with status code {r.status_code} and response: {r.json()}")
        return False



def cleanup(backup_slug):
    try:
        # Delete backup from supervisor
        SUPER_TOKEN = os.environ.get("SUPERVISOR_TOKEN")
        if not SUPER_TOKEN:
            raise EnvironmentError("SUPERVISOR_TOKEN environment variable not set")

        # Define the endpoint
        url = f"http://supervisor/backups/{backup_slug}"
        headers = {"Authorization": f"Bearer {SUPER_TOKEN}"}

        # Send POST request to create a full backup
        response = requests.delete(url, headers=headers)

        # Check for errors
        if not response.ok:
            raise Exception(f"Backup deletion failed: {response.status_code} {response.text}")

    except Exception as e:
        print(f"Unable to delete backup slug {backup_slug}: {e}")
        
def get_installed_addons():
    """
    Fetches the list of installed add-ons from the Home Assistant Supervisor API.
    """
    # Get the supervisor token from environment variable
    SUPER_TOKEN = os.environ.get("SUPERVISOR_TOKEN")
    if not SUPER_TOKEN:
        raise EnvironmentError("SUPERVISOR_TOKEN environment variable not set")

    # Define the endpoint for add-ons
    url = "http://supervisor/addons"
    headers = {
        "Authorization": f"Bearer {SUPER_TOKEN}",
        "Content-Type": "application/json"
    }

    # Send GET request to fetch add-on data
    response = requests.get(url, headers=headers)

    # Check for errors
    if not response.ok:
        raise Exception(f"Failed to fetch add-ons: {response.status_code} {response.text}")

    # Parse JSON response
    data = response.json()
    
    # The API returns the list under data -> addons
    # Since we are calling /addons, everything in this list is an installed addon.
    installed_addons = data.get("data", {}).get("addons", [])

    return installed_addons