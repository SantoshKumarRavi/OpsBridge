"""Send a synthetic alert through Alertmanager and verify its email in Mailpit."""

import json
import os
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone


alertmanager_url = os.getenv("ALERTMANAGER_URL", "http://localhost:9093").rstrip("/")
mailpit_url = os.getenv("MAILPIT_URL", "http://localhost:8025").rstrip("/")
alert_name = "OpsBridgeNotificationSmoke"
run_marker = os.getenv("GITHUB_RUN_ID", str(uuid.uuid4()))
alert = {
    "labels": {
        "alertname": alert_name,
        "severity": "warning",
        "verification_run": run_marker,
    },
    "annotations": {
        "summary": "Synthetic alert delivery verification",
        "description": "Confirms the local Alertmanager to SMTP inbox route.",
    },
    "startsAt": datetime.now(timezone.utc).isoformat(),
    "generatorURL": "https://github.com/opsbridge/observability-smoke",
}

request = urllib.request.Request(
    f"{alertmanager_url}/api/v2/alerts",
    data=json.dumps([alert]).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(request, timeout=10) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError(f"Alertmanager rejected smoke alert: HTTP {response.status}")
except urllib.error.HTTPError as exc:
    raise RuntimeError(f"Alertmanager rejected smoke alert: HTTP {exc.code} {exc.read().decode(errors='replace')}") from exc

deadline = time.monotonic() + 60
while time.monotonic() < deadline:
    with urllib.request.urlopen(f"{mailpit_url}/api/v1/messages?start=0&limit=50", timeout=10) as response:
        mailbox = json.load(response)
    messages = mailbox.get("messages", [])
    delivered = next((message for message in messages if alert_name in message.get("Subject", "")), None)
    if delivered:
        print(json.dumps({"status": "delivered", "alert": alert_name, "emailSubject": delivered["Subject"]}))
        break
    time.sleep(2)
else:
    raise SystemExit(f"No Mailpit email found for {alert_name} after 60 seconds")
