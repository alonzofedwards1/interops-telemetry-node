import json
import random
import time
import uuid
from datetime import datetime, timezone
import requests

API_URL = "http://localhost:8081/api/telemetry/events"

TOTAL_EVENTS = 500        # total events to send
BATCH_SIZE = 10           # events per burst
SLEEP_BETWEEN_BATCHES = 0.2  # seconds

CHANNELS = ["mirth-pd-01", "mirth-pd-02"]
ENVIRONMENTS = ["DEV", "QA"]
INTERACTIONS = ["PD-INT-TEST", "PD-INT-FAIL-001", "PD-INT-LOAD"]

def build_event():
    success = random.random() > 0.25  # 75% success rate

    return {
        "eventId": f"evt-{uuid.uuid4()}",
        "eventType": "pd.request.complete",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": {
            "system": "interop-control",
            "channelId": random.choice(CHANNELS),
            "environment": random.choice(ENVIRONMENTS),
        },
        "correlation": {
            "requestId": f"req-{uuid.uuid4()}",
            "messageId": f"msg-{uuid.uuid4()}",
        },
        "execution": {
            "durationMs": random.randint(50, 1500),
        },
        "outcome": {
            "status": "SUCCESS" if success else "FAILURE",
            "resultCount": random.randint(0, 25) if success else 0,
        },
        "protocol": {
            "standard": "FHIR",
            "interactionId": random.choice(INTERACTIONS),
        },
    }

def main():
    sent = 0

    while sent < TOTAL_EVENTS:
        batch = min(BATCH_SIZE, TOTAL_EVENTS - sent)

        for _ in range(batch):
            payload = build_event()
            r = requests.post(API_URL, json=payload)

            if r.status_code != 200:
                print("❌ Failed:", r.status_code, r.text)

            sent += 1

        print(f"✅ Sent {sent}/{TOTAL_EVENTS}")
        time.sleep(SLEEP_BETWEEN_BATCHES)

    print("🎉 Load test complete")

if __name__ == "__main__":
    main()
