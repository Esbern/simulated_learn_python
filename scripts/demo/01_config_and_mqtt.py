"""Demo: config + MQTT (similar to the notebook).

This script is intentionally beginner-friendly:
- Loads config from config.yaml (+ optional .env)
- Builds an example topic + JSON payload
- Optionally publishes ONE message (guarded by ENABLE_PUBLISH)

Run:
    python scripts/demo/01_config_and_mqtt.py

If imports fail, install the library first:
    pip install -e "."
"""

from __future__ import annotations

import json
import time

from simulated_city.config import load_config
from simulated_city.mqtt import MqttConnector, MqttPublisher


# Safety switch: publishing sends a real MQTT message.
# Keep this False unless you really want to publish.
ENABLE_PUBLISH = True


def main() -> None:
    cfg = load_config()

    events_topic = "simulated-city/events/demo"
    payload = json.dumps({"hello": "humtek"})

    print("MQTT broker:", f"{cfg.mqtt.host}:{cfg.mqtt.port}", "tls=", cfg.mqtt.tls)
    print("Example publish topic:", events_topic)
    print("Payload:", payload)

    if not ENABLE_PUBLISH:
        print("\nSkipping publish (ENABLE_PUBLISH is False).")
        print("To publish one message: set ENABLE_PUBLISH = True in this file.")
        return

    print("\nPublishing one message...")
    connector = MqttConnector(cfg.mqtt, client_id_suffix="demo-script")
    publisher = MqttPublisher(connector)
    try:
        connector.connect()
        if connector.wait_for_connection():
            publisher.publish_json(events_topic, payload, qos=1)
            print("Publish successful.")
            # Wait a moment for message to be sent
            time.sleep(0.1)
        else:
            print("Failed to connect to MQTT broker.")
    finally:
        if connector.client and connector.client.is_connected():
            connector.disconnect()


if __name__ == "__main__":
    main()
