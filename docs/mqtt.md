# MQTT

This template includes **paho-mqtt** by default and ships with a committed `config.yaml` that points at a HiveMQ-style broker configuration.

This document covers everything in `simulated_city.mqtt`:

- `MqttConnector`
- `MqttPublisher`

## Configure HiveMQ Cloud

1. Edit `config.yaml`:
   - Set `mqtt.host` to your HiveMQ cluster host (example: `xxxxxx.s1.eu.hivemq.cloud`)
   - Keep `mqtt.port: 8883` and `mqtt.tls: true`

2. Store credentials in a local `.env` file:

```bash
cp .env.example .env
# edit .env and set:
# HIVEMQ_USERNAME=...
# HIVEMQ_PASSWORD=...
```

## Connect from Python

```python
import time
from simulated_city.config import load_config
from simulated_city.mqtt import MqttConnector, MqttPublisher

cfg = load_config().mqtt

# Create a connector and connect
connector = MqttConnector(cfg, client_id_suffix="demo")
connector.connect()

# Wait for connection
if not connector.wait_for_connection():
    raise RuntimeError("Failed to connect to MQTT broker")

# Create a publisher and send a message
publisher = MqttPublisher(connector)
publisher.publish_json("simulated-city/metrics", '{"step": 1, "agents": 25}')

# Disconnect when done
time.sleep(1) # Give time for message to be sent
connector.disconnect()
```

Notes:

- `MqttConnector` handles the connection and automatic reconnection.
- You must call `connect()` to start the connection process.
- The network loop runs in a background thread.

## Classes

### `MqttConnector`

A class that manages the MQTT connection and provides automatic reconnection.

#### `__init__(self, cfg, client_id_suffix=None)`

Creates a new `MqttConnector`.

#### `connect()`

Starts the connection to the broker and begins the network loop in a background thread.

#### `disconnect()`

Disconnects the client from the broker and stops the network loop.

#### `wait_for_connection(timeout=10.0) -> bool`

Blocks until the client is connected, or until the timeout is reached. Returns `True` if connected, `False` otherwise.


### `MqttPublisher`

A simple class for publishing messages.

#### `__init__(self, connector)`

Creates a new `MqttPublisher` that uses the provided `MqttConnector`.

#### `publish_json(topic, payload, qos=0, retain=False)`

Publishes a JSON string to the given topic. This is a convenience method around paho’s `publish()`.

Example:

```python
# Assuming 'connector' is a connected MqttConnector instance
publisher = MqttPublisher(connector)
publisher.publish_json("my/topic", '{"data": 123}')
```

## Using other brokers

Projects can switch brokers by editing `config.yaml` (host/port/tls) or by loading a different config file.
