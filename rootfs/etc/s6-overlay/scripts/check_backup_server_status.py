# This code will query the Fleet Assistant backup server and check if it's time to create and upload a new backup.
import time
from datetime import datetime
import requests
import argparse
from helper_backup import create_backup, download_backup, upload_backup, cleanup
from helper_updates import check_update_available, upload_updates

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

        response = requests.get(URL, headers=headers, params=params, timeout=20)
        if response.status_code == 200:
            return response.json()['backup_needed']
        else:
            print(f"[{timestamp()}] [ERROR] Status code: {response.status_code}, detail: {response.text}")
            return "none"
            
    except Exception as e:
        print(f"[{timestamp()}] [EXCEPTION] {e}")
        return "none"


while True:
    try:
        backup_creation_needed = check_status()
        
        updates = check_update_available()
        print(f"[{datetime.now()}] Update status: {updates}")
        upload_updates(FleetAssistantServerIP, FleetToken, Installation_id, updates)

        if backup_creation_needed is True:
            backup_slug = create_backup()
            timestamp_str = datetime.now().strftime("%Y%m%d-%H%M%S")
            filename = f"/tmp/backup-{timestamp_str}.tar"

            download_backup(backup_slug, filename)
            upload_suceeded = upload_backup(FleetAssistantServerIP, FleetToken, Installation_id, filename)

            if upload_suceeded:
                cleanup(filename)
            else:
                print(f"[{datetime.now()}] Upload failed, not deleting {filename}")

        elif backup_creation_needed == "none":
            print(f"[{datetime.now()}] Error encountered in check_status.")

        else:
            pass

    except Exception as e:
        print(f"[{datetime.now()}] Critical error in loop: {e}")

    time.sleep(600)
