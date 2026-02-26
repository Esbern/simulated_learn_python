# Train Network Simulation

This document describes the train capacity simulation system for managing passenger flow during high-demand events (like football matches).

## Overview

The train network simulation models a five-station route where passengers board at entry stations and alight at exit stations. The system uses **agent-based programming** where independent agents (trains, passengers, sensors, control center, dispatcher) communicate via MQTT messages to coordinate operations.

### The Four Components

1. **Agents (Triggers)**: Passengers arrive at stations, trains move through the network
2. **Sensors**: Platform sensors count waiting passengers
3. **Control Center (Logic)**: Monitors sensor data and triggers extra train deployment
4. **Dispatcher (Response)**: Deploys additional trains when thresholds are exceeded

---

## Configuration System

### Configuration Files

The simulation is configured through two files:

**`config.yaml`** — Non-secret settings (committed to repository):
- Train specifications (capacity, departure interval, base occupancy)
- Route definition (5 stations with coordinates and exit percentages)
- Passenger flow rates (peak hours and off-peak)
- Dispatcher threshold for extra train deployment
- MQTT broker settings and topics

**`.env`** — Secrets (gitignored):
- MQTT credentials (username, password)

### Loading Configuration

```python
from simulated_city import load_config

config = load_config()

# Access train network configuration
train_capacity = config.train_network.train.capacity  # 300
threshold = config.train_network.dispatcher.waiting_threshold  # 250
route = config.train_network.route  # List of 5 stations
```

### Configuration Structure

#### Train Settings
- **Capacity**: 300 passengers per train
- **Departure interval**: 5 minutes between trains
- **Base occupancy**: 16% (48 passengers of non-event riders)

#### Route Stations
1. **Entry Station 1** — First pickup point (55.6761°N, 12.5683°E)
2. **Entry Station 2** — Second pickup point (55.6771°N, 12.5693°E)
3. **Entry Station 3** — Third pickup point (55.6781°N, 12.5703°E)
4. **Exit Station 1** — 75% of passengers alight (55.6791°N, 12.5713°E)
5. **Exit Station 2** — Remaining 25% of passengers alight (55.6801°N, 12.5723°E)

#### Passenger Flow Rates
Peak hours (passengers arriving every 10 minutes):
- **18:00**: 150 passengers
- **19:00**: 300 passengers
- **20:00**: 150 passengers
- **Off-peak**: 50 passengers

#### Dispatcher Rule
- **Threshold**: 250 waiting passengers triggers extra train deployment
- **Cooldown**: 5 minutes between dispatches for same station

---

## Data Models

All data models are defined in `simulated_city.agents` module.

### Core Data Structures

#### `Station`
Represents a station in the network.

```python
from simulated_city import Station

station = Station(
    name="Entry Station 1",
    station_type="entry",  # "entry" or "exit"
    location_lat=55.6761,
    location_lon=12.5683,
    exit_percentage=None,  # Only for exit stations
)
```

**Fields**:
- `name`: Station name
- `station_type`: "entry" (pickup) or "exit" (dropoff)
- `location_lat`, `location_lon`: Geographic coordinates
- `exit_percentage`: Percentage of passengers that alight (exit stations only)

**Validation**: Entry stations cannot have exit_percentage; exit stations must have it.

#### `Passenger`
Represents an individual passenger.

```python
from simulated_city import Passenger
from datetime import datetime

passenger = Passenger(
    id="station1-p123",
    entry_station="Entry Station 1",
    exit_station="Exit Station 1",
    arrival_time=datetime.now(),
    boarding_time=None,  # Set when passenger boards train
)

# Calculate wait time
wait_seconds = passenger.waiting_duration_seconds
```

**Fields**:
- `id`: Unique passenger identifier
- `entry_station`: Station where passenger entered
- `exit_station`: Station where passenger will exit
- `arrival_time`: When passenger arrived at station
- `boarding_time`: When passenger boarded train (None if still waiting)

**Properties**:
- `waiting_duration_seconds`: Time spent waiting (calculated property)

#### `Train`
Represents a train operating in the network.

```python
from simulated_city import Train, TrainStatus

train = Train(
    id="train-001",
    capacity=300,
    current_station_index=0,
    current_station_name="Entry Station 1",
    passengers_onboard=[],
    status=TrainStatus.IDLE,
    base_occupancy_count=48,  # 16% non-event passengers
)

# Check capacity
print(f"Available seats: {train.available_capacity}")
print(f"Capacity: {train.capacity_percentage:.1f}%")
print(f"Is full: {train.is_full}")
```

**Fields**:
- `id`: Unique train identifier
- `capacity`: Maximum passengers (300)
- `current_station_index`: Position in route (0-4)
- `current_station_name`: Name of current station
- `passengers_onboard`: List of Passenger objects
- `status`: TrainStatus enum (IDLE, IN_TRANSIT, AT_STATION, BOARDING, ALIGHTING)
- `base_occupancy_count`: Non-event passengers (constant)

**Properties**:
- `total_passengers`: Onboard + base occupancy
- `available_capacity`: Empty seats remaining
- `capacity_percentage`: Utilization as percentage
- `is_full`: True if at capacity

#### `StationQueue`
Tracks passengers waiting at a station platform.

```python
from simulated_city import StationQueue

queue = StationQueue(station_name="Entry Station 1")

# Add passengers
queue.add_passengers(new_passenger_list)

# Remove passengers (FIFO)
boarded = queue.remove_passengers(count=50)

# Check statistics
print(f"Waiting: {queue.count}")
print(f"Avg wait: {queue.average_wait_time_seconds:.1f}s")
```

**Fields**:
- `station_name`: Station this queue belongs to
- `waiting_passengers`: List of waiting passengers

**Properties**:
- `count`: Number of waiting passengers
- `average_wait_time_seconds`: Average wait time

**Methods**:
- `add_passengers(passengers)`: Add passengers to queue
- `remove_passengers(count)`: Remove and return passengers (FIFO)

#### `SimulationState`
Overall simulation state tracking.

```python
from simulated_city import SimulationState
from datetime import datetime

state = SimulationState(current_time=datetime.now())

# Add train
state.add_train(train)

# Access station queue
queue = state.get_station_queue("Entry Station 1")

# Check metrics
print(f"Active trains: {state.active_train_count}")
print(f"Total waiting: {state.total_waiting_passengers}")
print(f"Avg capacity: {state.average_train_capacity:.1f}%")
print(f"Generated: {state.total_passengers_generated}")
print(f"Boarded: {state.total_passengers_boarded}")
print(f"Alighted: {state.total_passengers_alighted}")
print(f"Extra trains: {state.extra_trains_deployed}")
```

**Fields**:
- `current_time`: Current simulation time
- `trains`: Dictionary of train_id → Train
- `station_queues`: Dictionary of station_name → StationQueue
- `total_passengers_generated`: Counter
- `total_passengers_boarded`: Counter
- `total_passengers_alighted`: Counter
- `extra_trains_deployed`: Counter

**Properties**:
- `active_train_count`: Number of trains in system
- `total_waiting_passengers`: Sum across all stations
- `average_train_capacity`: Average utilization across all trains

**Methods**:
- `get_station_queue(station_name)`: Get or create queue
- `add_train(train)`: Register new train
- `remove_train(train_id)`: Remove completed train

---

## Agent Classes

All agent classes are in `simulated_city.agents` module and communicate via MQTT.

### 1. TrainAgent

Manages a single train's movement and passenger operations.

**Initialization**:
```python
from simulated_city import TrainAgent, Train, Station
from simulated_city.mqtt import MqttPublisher

train_agent = TrainAgent(
    train=train,
    route=route_stations,  # List of Station objects
    mqtt_publisher=publisher,
    mqtt_base_topic="train_network",
)
```

**Key Methods**:

`pick_up_passengers(station_queue) -> int`
- Picks up passengers from queue up to available capacity
- Returns number of passengers that boarded
- Sets boarding_time on each passenger

`drop_off_passengers(station) -> int`
- Drops off passengers at exit stations
- Uses exit percentage to determine alighting count
- Returns number of passengers that alighted

`publish_status() -> None`
- Publishes train status to MQTT
- Topic: `train_network/train/{train_id}/status`
- Includes: position, capacity, passenger counts, coordinates

`async run(simulation_state, travel_time_seconds=30) -> None`
- Main agent loop
- Moves through route stations
- Handles boarding/alighting at each stop
- Publishes status updates
- Waits `travel_time_seconds` between stations

`stop() -> None`
- Stops the agent loop

**MQTT Messages Published**:
- Topic: `train_network/train/{train_id}/status`
- QoS: 0 (fire-and-forget for status updates)
- Payload:
  ```json
  {
    "train_id": "train-001",
    "status": "at_station",
    "station_name": "Entry Station 1",
    "station_index": 0,
    "station_lat": 55.6761,
    "station_lon": 12.5683,
    "passengers_onboard": 52,
    "base_occupancy": 48,
    "total_passengers": 100,
    "capacity": 300,
    "capacity_percentage": 33.3,
    "available_capacity": 200,
    "timestamp": "2026-02-25T10:30:45.123456"
  }
  ```

### 2. PassengerSourceAgent

Generates passengers at entry stations based on time of day.

**Initialization**:
```python
from simulated_city import PassengerSourceAgent

passenger_source = PassengerSourceAgent(
    station=entry_station,
    exit_stations=exit_station_list,
    passenger_flow_config=config.train_network.passenger_flow,
    mqtt_publisher=publisher,
    mqtt_base_topic="train_network",
)
```

**Key Methods**:

`get_arrival_rate(current_hour) -> int`
- Returns passengers per 10 minutes for given hour
- Checks peak hours configuration
- Falls back to off-peak rate

`generate_passengers(count) -> list[Passenger]`
- Creates new passenger objects
- Randomly assigns exit stations
- Returns list of passengers

`publish_arrival(passenger_count, queue_size) -> None`
- Publishes arrival event to MQTT
- Topic: `train_network/station/{station_name}/passengers/arrivals`

`async run(simulation_state, interval_seconds=60) -> None`
- Main agent loop
- Generates passengers based on time of day
- Adds passengers to station queue
- Updates simulation statistics
- Runs every `interval_seconds` (default: 60s)

`stop() -> None`
- Stops the agent loop

**MQTT Messages Published**:
- Topic: `train_network/station/{station_name}/passengers/arrivals`
- QoS: 0
- Payload:
  ```json
  {
    "station_name": "Entry Station 1",
    "new_arrivals": 30,
    "queue_size": 125,
    "timestamp": "2026-02-25T10:30:45.123456"
  }
  ```

### 3. SensorAgent

Monitors station platforms and reports passenger counts.

**Initialization**:
```python
from simulated_city import SensorAgent

sensor = SensorAgent(
    station=station,
    mqtt_publisher=publisher,
    mqtt_base_topic="train_network",
)
```

**Key Methods**:

`count_waiting(station_queue) -> int`
- Counts passengers in queue
- Returns waiting count

`publish_observation(waiting_count, avg_wait_time) -> None`
- Publishes sensor observation to MQTT
- Topic: `train_network/station/{station_name}/sensor/waiting_count`

`async run(simulation_state, interval_seconds=10) -> None`
- Main agent loop
- Reads station queue
- Publishes observations
- Runs every `interval_seconds` (default: 10s)

`stop() -> None`
- Stops the agent loop

**MQTT Messages Published**:
- Topic: `train_network/station/{station_name}/sensor/waiting_count`
- QoS: 0
- Payload:
  ```json
  {
    "station_name": "Entry Station 1",
    "waiting_count": 267,
    "avg_wait_time_seconds": 180.5,
    "timestamp": "2026-02-25T10:30:45.123456"
  }
  ```

### 4. ControlCenterAgent

Monitors sensor data and triggers dispatcher when threshold is exceeded.

**Initialization**:
```python
from simulated_city import ControlCenterAgent

control_center = ControlCenterAgent(
    dispatcher_config=config.train_network.dispatcher,
    mqtt_connector=connector,
    mqtt_publisher=publisher,
    mqtt_base_topic="train_network",
)
```

**Key Methods**:

`evaluate_threshold(station_name, waiting_count) -> bool`
- Checks if waiting count exceeds threshold (250)
- Prevents rapid repeated dispatches (5-minute cooldown)
- Returns True if extra train should be deployed

`request_extra_train(station_name, waiting_count) -> None`
- Publishes dispatch request to MQTT
- Topic: `train_network/control_center/dispatch_request`
- Uses QoS=1 for reliable delivery

`on_sensor_message(client, userdata, message) -> None`
- Callback for incoming sensor data
- Evaluates threshold
- Requests extra train if needed

`start() -> None`
- Subscribes to sensor topics
- Starts monitoring

`stop() -> None`
- Unsubscribes from topics
- Stops monitoring

**MQTT Messages Subscribed**:
- Topic: `train_network/station/+/sensor/waiting_count` (wildcard for all stations)
- QoS: 0

**MQTT Messages Published**:
- Topic: `train_network/control_center/dispatch_request`
- QoS: 1 (at-least-once delivery)
- Payload:
  ```json
  {
    "station_name": "Entry Station 1",
    "waiting_count": 267,
    "threshold": 250,
    "timestamp": "2026-02-25T10:30:45.123456"
  }
  ```

### 5. DispatcherAgent

Deploys extra trains in response to control center requests.

**Initialization**:
```python
from simulated_city import DispatcherAgent

dispatcher = DispatcherAgent(
    train_config=config.train_network.train,
    route=route_stations,
    mqtt_connector=connector,
    mqtt_publisher=publisher,
    mqtt_base_topic="train_network",
)
```

**Key Methods**:

`deploy_train(simulation_state) -> TrainAgent`
- Creates new train with proper base occupancy
- Adds train to simulation state
- Increments extra_trains_deployed counter
- Returns TrainAgent for the new train

`on_dispatch_request(client, userdata, message) -> None`
- Callback for dispatch requests from control center
- Deploys extra train
- Publishes deployment confirmation

`start(simulation_state) -> None`
- Subscribes to dispatch request topic
- Starts listening for requests

`stop() -> None`
- Stops all deployed train agents
- Unsubscribes from topics

`get_deployed_trains() -> dict[str, TrainAgent]`
- Returns dictionary of deployed extra trains

**MQTT Messages Subscribed**:
- Topic: `train_network/control_center/dispatch_request`
- QoS: 1

**MQTT Messages Published**:
- Topic: `train_network/dispatcher/train_deployed`
- QoS: 1
- Payload:
  ```json
  {
    "train_id": "train-extra-1",
    "station_name": "Entry Station 1",
    "waiting_count": 267,
    "timestamp": "2026-02-25T10:30:45.123456"
  }
  ```

---

## MQTT Communication

### Topic Structure

All topics are under the base `train_network/` namespace:

**Train Status**:
- `train_network/train/{train_id}/status` — Individual train updates

**Station Operations**:
- `train_network/station/{station_name}/passengers/arrivals` — Passenger arrivals
- `train_network/station/{station_name}/sensor/waiting_count` — Sensor observations

**Control & Dispatch**:
- `train_network/control_center/dispatch_request` — Request extra train
- `train_network/dispatcher/train_deployed` — Confirmation of deployment

### Message Flow

```
PassengerSourceAgent → arrivals → (station topic)
                                       ↓
SensorAgent → observations → sensor/waiting_count
                                       ↓
                            ControlCenterAgent
                                       ↓
                              dispatch_request
                                       ↓
                              DispatcherAgent
                                       ↓
                            deploys TrainAgent
                                       ↓
TrainAgent → status updates → train/{id}/status
```

### QoS Levels

- **QoS 0** (fire-and-forget): Status updates, sensor observations, arrivals
- **QoS 1** (at-least-once): Dispatch requests, deployment confirmations

---

## Usage Example

### Basic Setup

```python
import asyncio
from datetime import datetime
from simulated_city import (
    load_config,
    MqttConnector,
    MqttPublisher,
    Station,
    Train,
    SimulationState,
    TrainAgent,
    PassengerSourceAgent,
    SensorAgent,
    ControlCenterAgent,
    DispatcherAgent,
)

# Load configuration
config = load_config()

# Connect to MQTT
connector = MqttConnector(config.mqtt, client_id_suffix="simulation")
connector.connect()
connector.wait_for_connection(timeout=10.0)

publisher = MqttPublisher(connector)

# Create simulation state
state = SimulationState(current_time=datetime.now())

# Create stations from config
route_stations = []
for station_cfg in config.train_network.route:
    station = Station(
        name=station_cfg.name,
        station_type=station_cfg.type,
        location_lat=station_cfg.location.lat,
        location_lon=station_cfg.location.lon,
        exit_percentage=station_cfg.exit_percentage,
    )
    route_stations.append(station)

# Create initial train
base_occupancy = int(
    config.train_network.train.capacity *
    config.train_network.train.base_occupancy_percent / 100
)
train = Train(
    id="train-001",
    capacity=config.train_network.train.capacity,
    current_station_index=0,
    current_station_name=route_stations[0].name,
    base_occupancy_count=base_occupancy,
)
state.add_train(train)

# Create train agent
train_agent = TrainAgent(
    train=train,
    route=route_stations,
    mqtt_publisher=publisher,
    mqtt_base_topic=config.train_network.mqtt_base_topic,
)

# Create passenger sources for entry stations
passenger_sources = []
entry_stations = [s for s in route_stations if s.station_type == "entry"]
exit_stations = [s for s in route_stations if s.station_type == "exit"]

for entry_station in entry_stations:
    source = PassengerSourceAgent(
        station=entry_station,
        exit_stations=exit_stations,
        passenger_flow_config=config.train_network.passenger_flow,
        mqtt_publisher=publisher,
        mqtt_base_topic=config.train_network.mqtt_base_topic,
    )
    passenger_sources.append(source)

# Create sensors for all stations
sensors = []
for station in route_stations:
    sensor = SensorAgent(
        station=station,
        mqtt_publisher=publisher,
        mqtt_base_topic=config.train_network.mqtt_base_topic,
    )
    sensors.append(sensor)

# Create control center
control_center = ControlCenterAgent(
    dispatcher_config=config.train_network.dispatcher,
    mqtt_connector=connector,
    mqtt_publisher=publisher,
    mqtt_base_topic=config.train_network.mqtt_base_topic,
)

# Create dispatcher
dispatcher = DispatcherAgent(
    train_config=config.train_network.train,
    route=route_stations,
    mqtt_connector=connector,
    mqtt_publisher=publisher,
    mqtt_base_topic=config.train_network.mqtt_base_topic,
)

# Start control center and dispatcher
control_center.start()
dispatcher.start(state)

# Run simulation
async def run_simulation():
    # Start all agents concurrently
    tasks = [
        train_agent.run(state, travel_time_seconds=30),
        *[source.run(state, interval_seconds=60) for source in passenger_sources],
        *[sensor.run(state, interval_seconds=10) for sensor in sensors],
    ]
    
    await asyncio.gather(*tasks)

# Run the simulation
try:
    asyncio.run(run_simulation())
except KeyboardInterrupt:
    print("Simulation stopped")
finally:
    # Cleanup
    control_center.stop()
    dispatcher.stop()
    connector.disconnect()
```

---

## Implementation Status

### ✅ Completed (All Phases)

**Phase 1: Configuration & Infrastructure**
- [x] Extended `config.yaml` with train network settings
- [x] Added dataclasses to `config.py` (TrainConfig, PassengerFlowConfig, etc.)
- [x] Created data models in `agents.py` (Train, Passenger, Station, etc.)

**Phase 2: Core Agent Classes**
- [x] TrainAgent (movement, boarding, alighting, MQTT status)
- [x] PassengerSourceAgent (time-based passenger generation)
- [x] SensorAgent (platform monitoring)
- [x] ControlCenterAgent (threshold evaluation, dispatch requests)
- [x] DispatcherAgent (extra train deployment)

**Phase 3: Testing & Validation**
- [x] Unit tests for agent logic (`tests/test_agents.py` — 19 tests)
- [x] End-to-end smoke tests (`tests/test_train_simulation.py` — 3 tests)
- [x] MQTT message validation

**Phase 4: Exercise Notebooks**
- [x] `05_train_network_basics.ipynb` — Single train simulation
- [x] `05_train_passenger_source.ipynb` — Passenger generation
- [x] `05_train_control_center.ipynb` — Control logic
- [x] `05_train_full_simulation.ipynb` — Complete orchestration

**Phase 5: Visualization & Monitoring**
- [x] `05_train_map_viewer.ipynb` — Live map viewer with train positions
- [x] `05_train_dashboard.ipynb` — Real-time metrics dashboard with performance analysis

**Phase 6: Documentation & Exercises**
- [x] Train simulation documentation (this file)
- [x] Exercise prompts and solutions (`docs/exercises.md`)
- [x] Workshop notebooks with hands-on activities

---

## Next Steps

1. **Write tests** (`tests/test_agents.py`, `tests/test_train_simulation.py`)
2. **Create notebooks** to demonstrate agent usage interactively
3. **Add visualization** to show trains on map and queues at stations
4. **Document exercises** for students to experiment with parameters

---

## Troubleshooting

### MQTT Connection Issues

If agents cannot connect to MQTT broker:
1. Check `.env` file has valid credentials
2. Verify broker host/port in `config.yaml`
3. Test connection with: `python -m simulated_city`

### Configuration Not Loading

If `config.train_network` is None:
1. Ensure `config.yaml` has `train_network:` section
2. Check YAML syntax (indentation, colons)
3. Test with: `python -c "from simulated_city import load_config; print(load_config().train_network)"`

### Agent Not Publishing Messages

If messages don't appear:
1. Check MQTT connection is established: `connector.wait_for_connection()`
2. Verify topic structure matches expected format
3. Use MQTT client (like MQTT Explorer) to monitor topics
4. Check QoS level (agents use 0 or 1)

---

## References

- **Project repo**: `simulated_learn_python/`
- **Configuration**: `config.yaml`
- **Source code**: `src/simulated_city/agents.py`
- **Setup guide**: `docs/setup.md`
- **MQTT guide**: `docs/mqtt.md`
- **Overview**: `docs/overview.md`
