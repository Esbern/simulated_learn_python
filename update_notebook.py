import json

def update_notebook():
    with open('notebooks/01_simulated_city_basics.ipynb', 'r') as f:
        notebook = json.load(f)

    # Update cell 2
    notebook['cells'][1]['source'] = [
        "# Imports used in this notebook.
",
        "import json
",
        "import time
",
        "
",
        "from simulated_city.config import load_config
",
        "from simulated_city.mqtt import MqttConnector, MqttPublisher"
    ]

    # Update cell 5
    notebook['cells'][4]['source'] = [
        "# Define an example topic and payload.
",
        "events_topic = "simulated-city/events/demo"
",
        "payload = json.dumps({"hello": "humtek"})
",
        "
",
        "events_topic, payload"
    ]

    # Update cell 6
    notebook['cells'][5]['source'] = [
        "# Print where the notebook would publish (helps debugging).
",
        "print("MQTT broker:", f"{cfg.mqtt.host}:{cfg.mqtt.port}", "tls=", cfg.mqtt.tls)
",
        "print("Example publish topic:", events_topic)"
    ]

    # Update cell 8
    notebook['cells'][7]['source'] = [
        "# If enabled, publish ONE message.
",
        "if not ENABLE_PUBLISH:
",
        "    print("Skipping MQTT publish (ENABLE_PUBLISH is False).")
",
        "    print("To enable: set ENABLE_PUBLISH = True in Cell 3.")
",
        "else:
",
        "    connector = MqttConnector(cfg.mqtt, client_id_suffix="notebook")
",
        "    publisher = MqttPublisher(connector)
",
        "    try:
",
        "        connector.connect()
",
        "        if connector.wait_for_connection():
",
        "            print(f"Publishing to {events_topic}...")
",
        "            publisher.publish_json(events_topic, payload, qos=1)
",
        "            print("Publish successful.")
",
        "        else:
",
        "            print("Failed to connect to MQTT broker.")
",
        "    finally:
",
        "        if connector.client and connector.client.is_connected():
",
        "            connector.disconnect()"
    ]

    with open('notebooks/01_simulated_city_basics.ipynb', 'w') as f:
        json.dump(notebook, f, indent=1)

if __name__ == '__main__':
    update_notebook()
