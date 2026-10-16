
import os
import requests
from dotenv import load_dotenv

load_dotenv()

webhook_url = os.getenv("SLACK_WEBHOOK_URL")

if not webhook_url:
    raise RuntimeError("SLACK_WEBHOOK_URL was not loaded.")

message = """🚨 At Risk Incident

Type of Escalation: At Risk
Incident Date and Time: TEST DATE
AA Login: TEST_ALIAS
Shift Code: TEST_SHIFT
Process Path: TEST PROCESS
Area Injury Occurred: TEST AREA
Austin Case: TEST_CASE
Case Notes: This is a test message to verify Slack formatting.
"""
print("DEBUG: Identifier in message:", "E015GUGD2V6" in message)
print("DEBUG: Message:", repr(message))

response = requests.post(
    webhook_url,
    json={"text": message},
    timeout=15
)

print("HTTP status:", response.status_code)
print("Response:", response.text)
response.raise_for_status()
print("Test message submitted successfully.")
