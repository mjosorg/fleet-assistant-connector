# This code will query the Fleet Assistant backup server and check if it's time to create and upload a new backup.
import time
import requests
import argparse

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
print(f"Installation ID: {InstallationID}")

def check_status():
    try:
        headers = {"X-Token": FleetToken}
        params = {"installation_id": InstallationID}

        response = requests.get(URL, headers=headers, params=params, timeout=5)
        if response.status_code == 200:
            print(f"[OK] {response.json()['message']}")
        else:
            print(f"[ERROR] Status code: {response.status_code}, detail: {response.text}")
    except Exception as e:
        print(f"[EXCEPTION] {e}")


while True:
    print("Checking status...")
    check_status()
    print("Sleeping...")
    time.sleep(30)  # wait 10 minutes (600 seconds)
