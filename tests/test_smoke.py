import socket

import pytest

from simulated_city.config import load_config
from simulated_city.mqtt import MqttConnector, MqttPublisher


def is_broker_available(host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1)
    try:
        s.connect((host, port))
        s.close()
        return True
    except (socket.timeout, socket.error):
        return False


# Get default config to find broker host/port
default_config = load_config()
broker_available = is_broker_available(default_config.mqtt.host, default_config.mqtt.port)


@pytest.mark.skipif(not broker_available, reason=f"MQTT broker not available at {default_config.mqtt.host}:{default_config.mqtt.port}")
def test_mqtt_connection_and_publish():
    cfg = load_config()
    connector = MqttConnector(cfg.mqtt, client_id_suffix="test-smoke")
    try:
        connector.connect()
        assert connector.wait_for_connection(timeout=5), "Failed to connect to MQTT broker"

        publisher = MqttPublisher(connector)
        test_topic = "simulated-city/test/smoke"
        publisher.publish_json(test_topic, '{"test": "smoke"}', qos=1)

    finally:
        # Ensure disconnection even if asserts fail
        if connector.client and connector.client.is_connected():
            connector.disconnect()
