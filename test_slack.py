import os
import requests
from dotenv import load_dotenv

load_dotenv()

webhook_url = os.getenv("SLACK_WEBHOOK_URL")

response = requests.post(
    webhook_url,
    json={
        "text": "TEST: Austin Slack webhook payload is working."
    },
    timeout=15
)

print("HTTP status:", response.status_code)
print("Response:", response.text)
