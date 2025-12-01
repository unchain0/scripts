import os
import requests
import time

from dotenv import load_dotenv

load_dotenv()

user_id = os.getenv("HABITICA_USER_ID")
api_key = os.getenv("HABITICA_API_KEY")
client = os.getenv("HABITICA_CLIENT", f"{user_id}-Testing")
task_id = os.getenv("HABITICA_TASK_ID")
it = 9 ** 9
d = 1

h = {
    "x-api-user": user_id,
    "x-api-key": api_key,
    "x-client": client,
    "Content-Type": "application/json",
}
u = f"https://habitica.com/api/v3/tasks/{task_id}/score/up"

for i in range(it):
    r = requests.post(u, headers=h)
    print(f"{i + 1}: {r.status_code}")
    time.sleep(d)
