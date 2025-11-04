# This code will query the Fleet Assistant backup server and check if it's time to create and upload a new backup.
import time
import requests

URL = "http://127.0.0.1:8000/fleet_assistant_status"

def check_status():
    try:
        response = requests.get(URL, timeout=5)
        if response.status_code == 200:
            print(f"[OK] {response.json()['message']}")
        else:
            print(f"[ERROR] Status code: {response.status_code}")
    except Exception as e:
        print(f"[EXCEPTION] {e}")

if __name__ == "__main__":
    while True:
        check_status()
        time.sleep(600)  # wait 10 minutes (600 seconds)
