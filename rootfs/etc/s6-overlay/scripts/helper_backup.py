    # This is an example code for testing ha backup upload endpoint. 
import hashlib
import requests
import os 

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



def cleanup(file_source):
    try:
        os.remove(file_source)
    except FileNotFoundError:
        print(f"File not found: {file_source}")
    except Exception as e:
        print(f"Error deleting file {file_source}: {e}")
