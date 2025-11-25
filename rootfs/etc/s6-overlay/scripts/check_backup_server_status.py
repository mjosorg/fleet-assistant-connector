# This code will query the Fleet Assistant backup server and check if it's time to create and upload a new backup.
import time
import requests
import argparse
from helper_backup import create_backup

print("Invoking backup check script")


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

def check_status():
    try:
        headers = {"X-Token": FleetToken}
        params = {"installation_id": Installation_id}

        response = requests.get(URL, headers=headers, params=params, timeout=5)
        if response.status_code == 200:
            print(f"[OK] {response.json()['backup_needed']}")

            return response.json()['backup_needed']
        else:
            print(f"[ERROR] Status code: {response.status_code}, detail: {response.text}")
            return "none"
            
    except Exception as e:
        print(f"[EXCEPTION] {e}")


while True:
    backup_creation_needed = check_status()
    if backup_creation_needed == True:
        print("Triggering backup creation and upload...")
        backup_slug = create_backup()
        print(backup_slug)
    #    download_backup(backup_slug, "/tmp/backup.tar")
     #   upload_backup(FleetToken, Installation_id)
    else:
        print("No backup needed at this time.")

    print("Sleeping...")
    time.sleep(30)  # wait 10 minutes (600 seconds)
