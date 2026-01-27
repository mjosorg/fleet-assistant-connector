# This code will query the Fleet Assistant backup server and check if it's time to create and upload a new backup.
import time
from datetime import datetime
import requests
import argparse
from helper_backup import create_backup, download_backup, upload_backup, cleanup

parser = argparse.ArgumentParser(
    description="Trigger a backup via fleet assistant API"
)
parser.add_argument("--FleetAssistantServerIP", required=True, type=str)
parser.add_argument("--FleetToken", required=True, type=str)
parser.add_argument("--Installation_id", required=True, type=str)
args = parser.parse_args()

FleetAssistantServerIP = args.FleetAssistantServerIP
FleetToken = args.FleetToken
Installation_id = args.Installation_id

URL = f"http://{FleetAssistantServerIP}:8000/fleet_assistant_status"

print(f"Using Fleet Assistant server: {URL}")
print(f"Installation ID: {Installation_id}")

def timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def check_status():
    try:
        headers = {"X-Token": FleetToken}
        params = {"installation_id": Installation_id}

        response = requests.get(URL, headers=headers, params=params, timeout=30)
        if response.status_code == 200:
          
            return response.json()['backup_needed']
        else:
            print(f"[{timestamp()}] [ERROR] Status code: {response.status_code}, detail: {response.text}")
            return "none"
            
    except Exception as e:
        print(f"[{timestamp()}] [EXCEPTION] {e}")
        return "none"


while True:
    backup_creation_needed = check_status()
    if backup_creation_needed == True:
        backup_slug = create_backup()

        timestamp_filename = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"/tmp/backup-{timestamp_filename}.tar"

        download_backup(backup_slug, filename)

        upload_suceeded=upload_backup(FleetAssistantServerIP, FleetToken, Installation_id, filename)

        if upload_suceeded == True:
            cleanup(filename)
        else:
            print("Upload failed, not deleting local backup file.")
    
    elif backup_creation_needed == "none":
        # This handles your exceptions and non-200 status codes
        print(f"[{timestamp()}] [INFO] Error encountered. Waiting 10 minutes before retry...")

    else:
        # backup_creation_needed is False
        #print(f"[{timestamp()}] [INFO] No backup needed at this time.")
        continue

    time.sleep(600)
