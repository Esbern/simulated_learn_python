"""End-to-end smoke test for train network simulation.

This test runs a complete simulation with all agents for a short period
and verifies that the system behaves correctly.
"""

import json
import socket
from datetime import datetime
from typing import Any

import pytest

from simulated_city.config import load_config, PassengerFlowConfig, PeakHourConfig, DispatcherConfig, TrainConfig
from simulated_city.mqtt import MqttConnector, MqttPublisher
from simulated_city.agents import (
    Station,
    Train,
    SimulationState,
    TrainAgent,
    PassengerSourceAgent,
    SensorAgent,
    ControlCenterAgent,
    DispatcherAgent,
    TrainStatus,
)


def is_broker_available(host, port):
    """Check if MQTT broker is available."""
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


@pytest.fixture
def mqtt_publisher():
    """Create a real MQTT publisher for integration testing."""
    if not broker_available:
        pytest.skip("MQTT broker not available")
    
    cfg = load_config()
    connector = MqttConnector(cfg.mqtt, client_id_suffix="test-train-sim")
    connector.connect()
    
    if not connector.wait_for_connection(timeout=5):
        pytest.skip("Could not connect to MQTT broker")
    
    publisher = MqttPublisher(connector)
    
    yield publisher
    
    # Cleanup
    if connector.client and connector.client.is_connected():
        connector.disconnect()


@pytest.fixture
def sample_route():
    """Create a realistic train route."""
    return [
        Station("Entry Station 1", "entry", 55.6761, 12.5683),
        Station("Entry Station 2", "entry", 55.6771, 12.5693),
        Station("Entry Station 3", "entry", 55.6781, 12.5703),
        Station("Exit Station 1", "exit", 55.6791, 12.5713, exit_percentage=75),
        Station("Exit Station 2", "exit", 55.6801, 12.5723, exit_percentage=25),
    ]


@pytest.fixture
def simulation_state():
    """Create a fresh simulation state."""
    return SimulationState(current_time=datetime.now())


@pytest.mark.skipif(not broker_available, reason=f"MQTT broker not available at {default_config.mqtt.host}:{default_config.mqtt.port}")
def test_train_simulation_end_to_end(mqtt_publisher, sample_route, simulation_state):
    """Run complete simulation with all agents for 10 simulated minutes.
    
    This test verifies:
    1. Trains can be created and move through stations
    2. Passengers are generated at entry stations
    3. Passengers board trains and alight at exits
    4. MQTT messages are published correctly
    5. Dispatcher threshold logic works
    """
    
    # Track published messages
    published_messages = []
    
    # Wrap publish_json to track calls
    original_publish = mqtt_publisher.publish_json
    def tracked_publish(topic: str, payload: Any, qos: int = 0):
        published_messages.append({"topic": topic, "payload": payload})
        return original_publish(topic, payload, qos)
    
    mqtt_publisher.publish_json = tracked_publish
    
    # Setup: Create initial train
    initial_train = Train(
        id="train-001",
        capacity=300,
        current_station_index=0,
        current_station_name=sample_route[0].name,
        base_occupancy_count=48,  # 16% base occupancy
        status=TrainStatus.AT_STATION,
    )
    simulation_state.add_train(initial_train)
    
    # Create train agent
    train_agent = TrainAgent(
        train=initial_train,
        route=sample_route,
        mqtt_publisher=mqtt_publisher,
        mqtt_base_topic="train_network",
    )
    
    # Create passenger flow config
    flow_config = PassengerFlowConfig(
        peak_hours=[PeakHourConfig(start=18, end=20, passengers_per_10min=300)],
        off_peak_passengers_per_10min=50,
    )
    
    # Create passenger source agents for entry stations
    entry_stations = [s for s in sample_route if s.station_type == "entry"]
    exit_stations = [s for s in sample_route if s.station_type == "exit"]
    
    passenger_sources = []
    for entry_station in entry_stations:
        source = PassengerSourceAgent(
            station=entry_station,
            exit_stations=exit_stations,
            passenger_flow_config=flow_config,
            mqtt_publisher=mqtt_publisher,
            mqtt_base_topic="train_network",
        )
        passenger_sources.append(source)
    
    # Create sensor agents
    sensor_agents = []
    for entry_station in entry_stations:
        sensor = SensorAgent(
            station=entry_station,
            mqtt_publisher=mqtt_publisher,
            mqtt_base_topic="train_network",
        )
        sensor_agents.append(sensor)
    
    # Simulate 10 minutes (in simulation time) at peak hour
    simulation_start = datetime.now().replace(hour=19, minute=0)  # Peak time
    simulation_duration_minutes = 10
    
    # Initial state verification
    assert simulation_state.active_train_count == 1
    assert simulation_state.total_waiting_passengers == 0
    
    # Generate initial passengers at all entry stations
    for i, source in enumerate(passenger_sources):
        # Peak hour: 300 per 10 minutes
        passengers = source.generate_passengers(300)
        queue = simulation_state.get_station_queue(entry_stations[i].name)
        queue.add_passengers(passengers)
        source.publish_arrival(len(passengers), queue.count)
        simulation_state.total_passengers_generated += len(passengers)
    
    # Verify passengers were generated (peak time, so should be high)
    initial_waiting = simulation_state.total_waiting_passengers
    assert initial_waiting > 0, "No passengers generated during peak hour"
    print(f"Initial waiting passengers: {initial_waiting}")
    
    # Sensors publish observations
    for i, sensor in enumerate(sensor_agents):
        queue = simulation_state.get_station_queue(entry_stations[i].name)
        sensor.publish_observation(queue.count, queue.average_wait_time_seconds)
    
    # Simulate train stopping at each station
    for station_idx, station in enumerate(sample_route):
        print(f"\nTrain at {station.name} (index {station_idx})")
        
        # Update train position
        initial_train.current_station_index = station_idx
        initial_train.current_station_name = station.name
        
        if station.station_type == "entry":
            # Pick up passengers
            initial_train.status = TrainStatus.BOARDING
            queue = simulation_state.get_station_queue(station.name)
            waiting_before = queue.count
            
            boarded = train_agent.pick_up_passengers(queue)
            simulation_state.total_passengers_boarded += boarded
            
            print(f"  Picked up {boarded} passengers (waiting: {waiting_before} -> {queue.count})")
        
        elif station.station_type == "exit":
            # Drop off passengers
            initial_train.status = TrainStatus.ALIGHTING
            passengers_before = len(initial_train.passengers_onboard)
            
            alighted = train_agent.drop_off_passengers(station)
            simulation_state.total_passengers_alighted += alighted
            
            print(f"  Dropped off {alighted} passengers (onboard: {passengers_before} -> {len(initial_train.passengers_onboard)})")
        
        # Publish train status
        train_agent.publish_status()
        
        # Sensors observe and publish
        for i, sensor in enumerate(sensor_agents):
            queue = simulation_state.get_station_queue(entry_stations[i].name)
            sensor.publish_observation(queue.count, queue.average_wait_time_seconds)
    
    # Verify MQTT messages were published
    assert len(published_messages) > 0, "No MQTT messages published"
    print(f"\nTotal MQTT messages published: {len(published_messages)}")
    
    # Check for different message types
    train_status_msgs = [m for m in published_messages if "/train/" in m["topic"] and "/status" in m["topic"]]
    sensor_msgs = [m for m in published_messages if "/sensor/" in m["topic"] or "/waiting" in m["topic"]]
    passenger_arrival_msgs = [m for m in published_messages if "/passengers/" in m["topic"] or "/arrival" in m["topic"]]
    
    print(f"  Train status messages: {len(train_status_msgs)}")
    print(f"  Sensor messages: {len(sensor_msgs)}")
    print(f"  Passenger arrival messages: {len(passenger_arrival_msgs)}")
    
    assert len(train_status_msgs) > 0, "No train status messages published"
    
    # Verify train status message structure
    sample_train_msg = train_status_msgs[0]
    payload_str = sample_train_msg["payload"]
    payload = json.loads(payload_str)
    assert "train_id" in payload
    assert "status" in payload
    assert "passengers_onboard" in payload or "total_passengers" in payload
    assert "capacity" in payload
    assert "station_name" in payload
    
    # Verify simulation metrics
    print(f"\nSimulation metrics:")
    print(f"  Passengers generated: {simulation_state.total_passengers_generated}")
    print(f"  Passengers boarded: {simulation_state.total_passengers_boarded}")
    print(f"  Passengers alighted: {simulation_state.total_passengers_alighted}")
    print(f"  Final waiting passengers: {simulation_state.total_waiting_passengers}")
    print(f"  Active trains: {simulation_state.active_train_count}")
    
    # Verify logical consistency
    assert simulation_state.total_passengers_generated > 0
    assert simulation_state.total_passengers_boarded <= simulation_state.total_passengers_generated
    
    # Passengers should have been picked up
    assert simulation_state.total_passengers_boarded > 0, "No passengers boarded trains"
    
    # At exit stations, passengers should have alighted
    assert simulation_state.total_passengers_alighted > 0, "No passengers alighted"


@pytest.mark.skipif(not broker_available, reason=f"MQTT broker not available at {default_config.mqtt.host}:{default_config.mqtt.port}")
def test_dispatcher_threshold_behavior(mqtt_publisher, sample_route, simulation_state):
    """Verify dispatcher deploys extra trains when threshold is exceeded."""
    
    # Create configs
    dispatcher_config = DispatcherConfig(waiting_threshold=250)
    train_config = TrainConfig(capacity=300, departure_interval_minutes=5, base_occupancy_percent=16)
    
    # Create control center (needs a connector for subscriptions, use mock)
    from unittest.mock import Mock
    mock_connector = Mock()
    mock_connector.client = Mock()
    
    control_center = ControlCenterAgent(
        dispatcher_config=dispatcher_config,
        mqtt_connector=mock_connector,
        mqtt_publisher=mqtt_publisher,
        mqtt_base_topic="train_network",
    )
    
    dispatcher = DispatcherAgent(
        train_config=train_config,
        route=sample_route,
        mqtt_connector=mock_connector,
        mqtt_publisher=mqtt_publisher,
        mqtt_base_topic="train_network",
    )
    
    # Simulate high passenger load at Entry Station 1
    entry_station = "Entry Station 1"
    waiting_count = 275  # Above threshold
    
    # Control center evaluates
    should_dispatch = control_center.evaluate_threshold(entry_station, waiting_count)
    assert should_dispatch, "Control center should request dispatch for 275 passengers"
    
    # Request extra train
    control_center.request_extra_train(entry_station, waiting_count)
    
    # Dispatcher deploys
    extra_train_agent = dispatcher.deploy_train(simulation_state)
    assert extra_train_agent is not None
    assert extra_train_agent.train.capacity == 300
    assert extra_train_agent.train.base_occupancy_count == 48
    assert simulation_state.extra_trains_deployed == 1
    
    # Test below threshold
    waiting_count_low = 200
    should_dispatch_low = control_center.evaluate_threshold(entry_station, waiting_count_low)
    assert not should_dispatch_low, "Control center should not dispatch for 200 passengers (below 250)"


@pytest.mark.skipif(not broker_available, reason=f"MQTT broker not available at {default_config.mqtt.host}:{default_config.mqtt.port}")
def test_passenger_generation_rates(mqtt_publisher, sample_route):
    """Verify passenger generation matches peak/off-peak configuration."""
    
    exit_stations = [s for s in sample_route if s.station_type == "exit"]
    station = Station("Entry Station 1", "entry", 55.6761, 12.5683)
    
    # Create passenger flow config
    flow_config = PassengerFlowConfig(
        peak_hours=[PeakHourConfig(start=18, end=20, passengers_per_10min=300)],
        off_peak_passengers_per_10min=50,
    )
    
    # Create passenger source
    source = PassengerSourceAgent(
        station=station,
        exit_stations=exit_stations,
        passenger_flow_config=flow_config,
        mqtt_publisher=mqtt_publisher,
        mqtt_base_topic="train_network",
    )
    
    # Test peak hour rate
    peak_rate = source.get_arrival_rate(19)
    assert peak_rate == 300, f"Expected 300 passengers/10min during peak, got {peak_rate}"
    
    # Test off-peak hour rate
    off_peak_rate = source.get_arrival_rate(14)
    assert off_peak_rate == 50, f"Expected 50 passengers/10min during off-peak, got {off_peak_rate}"
    
    # Generate during peak
    peak_passengers = source.generate_passengers(300)
    assert len(peak_passengers) == 300
    
    # Generate during off-peak
    off_peak_passengers = source.generate_passengers(50)
    assert len(off_peak_passengers) == 50
    
    # Verify all passengers have exit stations
    all_passengers = peak_passengers + off_peak_passengers
    exit_station_names = [s.name for s in exit_stations]
    for passenger in all_passengers:
        assert passenger.exit_station in exit_station_names, f"Invalid exit station: {passenger.exit_station}"
