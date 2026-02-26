"""Unit tests for train simulation agents.

Tests verify core logic of train operations, passenger generation,
and dispatcher threshold rules.
"""

import json
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, call

import pytest

from simulated_city.agents import (
    Station,
    Passenger,
    Train,
    StationQueue,
    SimulationState,
    TrainAgent,
    PassengerSourceAgent,
    SensorAgent,
    ControlCenterAgent,
    DispatcherAgent,
    TrainStatus,
)
from simulated_city.config import (
    PassengerFlowConfig,
    PeakHourConfig,
    DispatcherConfig,
    TrainConfig,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_route():
    """Create a sample train route with entry and exit stations."""
    return [
        Station("Entry Station 1", "entry", 55.6761, 12.5683),
        Station("Entry Station 2", "entry", 55.6771, 12.5693),
        Station("Entry Station 3", "entry", 55.6781, 12.5703),
        Station("Exit Station 1", "exit", 55.6791, 12.5713, exit_percentage=75),
        Station("Exit Station 2", "exit", 55.6801, 12.5723, exit_percentage=25),
    ]


@pytest.fixture
def sample_train(sample_route):
    """Create a sample train."""
    return Train(
        id="train-001",
        capacity=300,
        current_station_index=0,
        current_station_name=sample_route[0].name,
        base_occupancy_count=48,  # 16% of 300
    )


@pytest.fixture
def mock_mqtt_publisher():
    """Create a mock MQTT publisher."""
    mock_pub = Mock()
    mock_pub.publish_json = Mock()
    return mock_pub


@pytest.fixture
def sample_simulation_state(sample_route):
    """Create a sample simulation state."""
    state = SimulationState(current_time=datetime.now())
    # Initialize station queues for entry stations
    for station in sample_route:
        if station.station_type == "entry":
            state.get_station_queue(station.name)
    return state


# =============================================================================
# Data Model Tests
# =============================================================================


def test_station_exit_percentage_validation():
    """Exit stations must have exit_percentage, entry stations must not."""
    # Valid exit station
    exit_station = Station("Exit 1", "exit", 55.0, 12.0, exit_percentage=75)
    assert exit_station.exit_percentage == 75
    
    # Valid entry station
    entry_station = Station("Entry 1", "entry", 55.0, 12.0)
    assert entry_station.exit_percentage is None
    
    # Invalid: exit station without percentage
    with pytest.raises(ValueError, match="must have exit_percentage"):
        Station("Exit Bad", "exit", 55.0, 12.0)
    
    # Invalid: entry station with percentage
    with pytest.raises(ValueError, match="should not have exit_percentage"):
        Station("Entry Bad", "entry", 55.0, 12.0, exit_percentage=50)


def test_passenger_waiting_duration():
    """Passenger waiting duration calculates correctly before and after boarding."""
    arrival = datetime.now() - timedelta(seconds=120)
    passenger = Passenger(
        id="p-001",
        entry_station="Entry 1",
        exit_station="Exit 1",
        arrival_time=arrival,
    )
    
    # Before boarding: should be ~120 seconds
    wait_time = passenger.waiting_duration_seconds
    assert 119 <= wait_time <= 121  # Allow 1 second tolerance
    
    # After boarding
    passenger.boarding_time = datetime.now()
    wait_time = passenger.waiting_duration_seconds
    assert 119 <= wait_time <= 121


def test_train_capacity_calculations(sample_train):
    """Train capacity calculations include base occupancy."""
    # Initially: 48 base occupancy, 0 event passengers
    assert sample_train.total_passengers == 48
    assert sample_train.available_capacity == 252
    assert sample_train.capacity_percentage == 16.0
    assert not sample_train.is_full
    
    # Add event passengers
    for i in range(200):
        passenger = Passenger(
            id=f"p-{i}",
            entry_station="Entry 1",
            exit_station="Exit 1",
            arrival_time=datetime.now(),
        )
        sample_train.passengers_onboard.append(passenger)
    
    assert sample_train.total_passengers == 248  # 48 + 200
    assert sample_train.available_capacity == 52
    assert round(sample_train.capacity_percentage, 1) == 82.7
    assert not sample_train.is_full
    
    # Fill to capacity
    for i in range(200, 252):
        passenger = Passenger(
            id=f"p-{i}",
            entry_station="Entry 1",
            exit_station="Exit 1",
            arrival_time=datetime.now(),
        )
        sample_train.passengers_onboard.append(passenger)
    
    assert sample_train.total_passengers == 300  # 48 + 252
    assert sample_train.available_capacity == 0
    assert sample_train.capacity_percentage == 100.0
    assert sample_train.is_full


def test_station_queue_operations():
    """Station queue adds and removes passengers correctly (FIFO)."""
    queue = StationQueue(station_name="Entry 1")
    assert queue.count == 0
    assert queue.average_wait_time_seconds == 0.0
    
    # Add passengers
    passengers = [
        Passenger(f"p-{i}", "Entry 1", "Exit 1", datetime.now() - timedelta(seconds=i*10))
        for i in range(5)
    ]
    queue.add_passengers(passengers)
    assert queue.count == 5
    
    # Average wait time should be non-zero
    avg_wait = queue.average_wait_time_seconds
    assert avg_wait > 0
    
    # Remove passengers (FIFO)
    removed = queue.remove_passengers(3)
    assert len(removed) == 3
    assert removed[0].id == "p-0"  # First in
    assert removed[1].id == "p-1"
    assert removed[2].id == "p-2"
    assert queue.count == 2
    
    # Remove more than available
    removed = queue.remove_passengers(10)
    assert len(removed) == 2
    assert queue.count == 0


def test_simulation_state_metrics(sample_simulation_state, sample_route):
    """Simulation state tracks metrics correctly."""
    state = sample_simulation_state
    
    # Initially empty
    assert state.active_train_count == 0
    assert state.total_waiting_passengers == 0
    assert state.average_train_capacity == 0.0
    
    # Add trains
    train1 = Train("t1", 300, 0, sample_route[0].name, base_occupancy_count=60)
    train2 = Train("t2", 300, 0, sample_route[0].name, base_occupancy_count=120)
    state.add_train(train1)
    state.add_train(train2)
    
    assert state.active_train_count == 2
    # Average capacity: (60/300)*100 + (120/300)*100 = 20 + 40 = 60 / 2 = 30
    assert state.average_train_capacity == 30.0
    
    # Add waiting passengers
    entry_queue = state.get_station_queue("Entry Station 1")
    entry_queue.add_passengers([
        Passenger(f"p-{i}", "Entry Station 1", "Exit Station 1", datetime.now())
        for i in range(50)
    ])
    assert state.total_waiting_passengers == 50
    
    # Remove train
    removed = state.remove_train("t1")
    assert removed.id == "t1"
    assert state.active_train_count == 1


# =============================================================================
# TrainAgent Tests
# =============================================================================


def test_train_agent_pick_up_passengers(sample_train, sample_route, mock_mqtt_publisher):
    """TrainAgent picks up passengers up to available capacity."""
    agent = TrainAgent(sample_train, sample_route, mock_mqtt_publisher)
    
    # Create station queue with passengers
    queue = StationQueue(station_name="Entry Station 1")
    passengers = [
        Passenger(f"p-{i}", "Entry Station 1", "Exit Station 1", datetime.now())
        for i in range(100)
    ]
    queue.add_passengers(passengers)
    
    assert queue.count == 100
    assert sample_train.available_capacity == 252  # 300 - 48 base
    
    # Pick up passengers
    boarded_count = agent.pick_up_passengers(queue)
    
    assert boarded_count == 100  # All 100 fit
    assert queue.count == 0
    assert len(sample_train.passengers_onboard) == 100
    assert sample_train.available_capacity == 152
    
    # All boarded passengers should have boarding_time set
    for p in sample_train.passengers_onboard:
        assert p.boarding_time is not None


def test_train_agent_pick_up_when_full(sample_train, sample_route, mock_mqtt_publisher):
    """TrainAgent cannot pick up passengers when at capacity."""
    agent = TrainAgent(sample_train, sample_route, mock_mqtt_publisher)
    
    # Fill train to capacity
    for i in range(252):  # 300 - 48 base
        sample_train.passengers_onboard.append(
            Passenger(f"p-{i}", "Entry 1", "Exit 1", datetime.now())
        )
    
    assert sample_train.is_full
    
    # Create queue
    queue = StationQueue(station_name="Entry Station 1")
    queue.add_passengers([
        Passenger("p-new", "Entry Station 1", "Exit Station 1", datetime.now())
    ])
    
    # Try to pick up
    boarded_count = agent.pick_up_passengers(queue)
    
    assert boarded_count == 0
    assert queue.count == 1  # Passenger still waiting


def test_train_agent_drop_off_passengers_at_exit(sample_train, sample_route, mock_mqtt_publisher):
    """TrainAgent drops off passengers at exit stations based on exit percentage."""
    agent = TrainAgent(sample_train, sample_route, mock_mqtt_publisher)
    
    # Add passengers with various exit stations
    exit1_station_name = "Exit Station 1"
    exit2_station_name = "Exit Station 2"
    
    # Add 100 passengers, 20 explicitly for Exit Station 1
    for i in range(20):
        sample_train.passengers_onboard.append(
            Passenger(f"p-{i}", "Entry 1", exit1_station_name, datetime.now())
        )
    # Add 80 more passengers for Exit Station 2
    for i in range(20, 100):
        sample_train.passengers_onboard.append(
            Passenger(f"p-{i}", "Entry 1", exit2_station_name, datetime.now())
        )
    
    assert len(sample_train.passengers_onboard) == 100
    
    # Move train to Exit Station 1 (75% exit rate)
    sample_train.current_station_index = 3
    sample_train.current_station_name = exit1_station_name
    exit_station = sample_route[3]
    
    # Drop off passengers
    alighted_count = agent.drop_off_passengers(exit_station)
    
    # Should drop off at least 20 (those targeted) or 75% of 100 = 75
    assert alighted_count == 75  # Max of 20 and 75
    assert len(sample_train.passengers_onboard) == 25


def test_train_agent_no_drop_off_at_entry(sample_train, sample_route, mock_mqtt_publisher):
    """TrainAgent does not drop off passengers at entry stations."""
    agent = TrainAgent(sample_train, sample_route, mock_mqtt_publisher)
    
    # Add passengers
    sample_train.passengers_onboard.append(
        Passenger("p-1", "Entry 1", "Exit 1", datetime.now())
    )
    
    # At entry station
    entry_station = sample_route[0]
    alighted_count = agent.drop_off_passengers(entry_station)
    
    assert alighted_count == 0
    assert len(sample_train.passengers_onboard) == 1


def test_train_agent_publish_status(sample_train, sample_route, mock_mqtt_publisher):
    """TrainAgent publishes correct status message structure."""
    agent = TrainAgent(sample_train, sample_route, mock_mqtt_publisher, mqtt_base_topic="train_network")
    
    # Add some passengers
    for i in range(50):
        sample_train.passengers_onboard.append(
            Passenger(f"p-{i}", "Entry 1", "Exit 1", datetime.now())
        )
    
    sample_train.status = TrainStatus.BOARDING
    
    # Publish status
    agent.publish_status()
    
    # Verify MQTT publish was called
    assert mock_mqtt_publisher.publish_json.called
    call_args = mock_mqtt_publisher.publish_json.call_args
    
    # Check topic
    topic = call_args[0][0]
    assert topic == "train_network/train/train-001/status"
    
    # Check payload structure (payload is JSON string)
    payload_str = call_args[0][1]
    payload = json.loads(payload_str)
    assert "train_id" in payload
    assert payload["train_id"] == "train-001"
    assert payload["status"] == "boarding"
    assert payload["passengers_onboard"] == 50
    assert payload["base_occupancy"] == 48
    assert payload["total_passengers"] == 98
    assert payload["capacity"] == 300
    assert "capacity_percentage" in payload
    assert "timestamp" in payload


# =============================================================================
# PassengerSourceAgent Tests
# =============================================================================


def test_passenger_source_generates_correct_count():
    """PassengerSourceAgent generates passengers and checks arrival rates."""
    mock_publisher = Mock()
    station = Station("Entry Station 1", "entry", 55.6761, 12.5683)
    exit_stations = [Station("Exit 1", "exit", 55.7, 12.6, exit_percentage=100)]
    
    # Create passenger flow config
    flow_config = PassengerFlowConfig(
        peak_hours=[PeakHourConfig(start=18, end=20, passengers_per_10min=300)],
        off_peak_passengers_per_10min=50,
    )
    
    # Create agent
    agent = PassengerSourceAgent(
        station=station,
        exit_stations=exit_stations,
        passenger_flow_config=flow_config,
        mqtt_publisher=mock_publisher,
        mqtt_base_topic="train_network",
    )
    
    # Test off-peak rate getter
    off_peak_rate = agent.get_arrival_rate(14)
    assert off_peak_rate == 50
    
    # Test peak rate getter
    peak_rate = agent.get_arrival_rate(19)
    assert peak_rate == 300
    
    # Test passenger generation
    passengers = agent.generate_passengers(100)
    assert len(passengers) == 100


def test_passenger_source_assigns_exit_stations():
    """PassengerSourceAgent assigns exit stations with correct distribution."""
    mock_publisher = Mock()
    station = Station("Entry Station 1", "entry", 55.6761, 12.5683)
    exit_stations = [
        Station("Exit Station 1", "exit", 55.7, 12.6, exit_percentage=75),
        Station("Exit Station 2", "exit", 55.8, 12.7, exit_percentage=25),
    ]
    exit_station_names = [s.name for s in exit_stations]
    
    flow_config = PassengerFlowConfig(
        peak_hours=[],
        off_peak_passengers_per_10min=100,
    )
    
    agent = PassengerSourceAgent(
        station=station,
        exit_stations=exit_stations,
        passenger_flow_config=flow_config,
        mqtt_publisher=mock_publisher,
    )
    
    # Generate many passengers
    passengers = agent.generate_passengers(100)
    assert len(passengers) == 100
    
    # All should have exit station assigned
    assert all(p.exit_station in exit_station_names for p in passengers)
    
    # Check IDs are unique
    ids = [p.id for p in passengers]
    assert len(ids) == len(set(ids))


def test_passenger_source_publish_arrival():
    """PassengerSourceAgent publishes arrival messages correctly."""
    mock_publisher = Mock()
    station = Station("Entry Station 1", "entry", 55.6761, 12.5683)
    exit_stations = [Station("Exit 1", "exit", 55.7, 12.6, exit_percentage=100)]
    
    flow_config = PassengerFlowConfig(
        peak_hours=[],
        off_peak_passengers_per_10min=50,
    )
    
    agent = PassengerSourceAgent(
        station=station,
        exit_stations=exit_stations,
        passenger_flow_config=flow_config,
        mqtt_publisher=mock_publisher,
        mqtt_base_topic="train_network",
    )
    
    # Publish arrival (takes passenger count and queue size)
    agent.publish_arrival(10, 50)
    
    # Verify publish was called
    assert mock_publisher.publish_json.called
    call_args = mock_publisher.publish_json.call_args
    
    # Check topic
    topic = call_args[0][0]
    assert "Entry Station 1" in topic
    assert "passengers" in topic or "arrivals" in topic
    
    # Check payload (is JSON string)
    payload_str = call_args[0][1]
    payload = json.loads(payload_str)
    assert "new_arrivals" in payload or "count" in payload


# =============================================================================
# SensorAgent Tests
# =============================================================================


def test_sensor_agent_counts_waiting_passengers():
    """SensorAgent correctly counts waiting passengers at a station."""
    mock_publisher = Mock()
    sim_state = SimulationState(current_time=datetime.now())
    station = Station("Entry Station 1", "entry", 55.6761, 12.5683)
    
    agent = SensorAgent(
        station=station,
        mqtt_publisher=mock_publisher,
        mqtt_base_topic="train_network",
    )
    
    # Create queue and test counting
    queue = sim_state.get_station_queue("Entry Station 1")
    
    # Initially zero
    count = agent.count_waiting(queue)
    assert count == 0
    
    # Add passengers to queue
    queue.add_passengers([
        Passenger(f"p-{i}", "Entry Station 1", "Exit 1", datetime.now())
        for i in range(75)
    ])
    
    count = agent.count_waiting(queue)
    assert count == 75


def test_sensor_agent_publish_observation():
    """SensorAgent publishes waiting count to correct topic."""
    mock_publisher = Mock()
    station = Station("Entry Station 1", "entry", 55.6761, 12.5683)
    
    agent = SensorAgent(
        station=station,
        mqtt_publisher=mock_publisher,
        mqtt_base_topic="train_network",
    )
    
    # Publish observation (takes waiting count and avg wait time)
    agent.publish_observation(120, 45.5)
    
    # Verify publish
    assert mock_publisher.publish_json.called
    call_args = mock_publisher.publish_json.call_args
    
    # Check topic structure
    topic = call_args[0][0]
    assert "train_network" in topic
    assert "station" in topic
    assert "sensor" in topic or "waiting" in topic
    
    # Check payload (is JSON string)
    payload_str = call_args[0][1]
    payload = json.loads(payload_str)
    assert "waiting_count" in payload
    assert payload["waiting_count"] == 120
    assert "avg_wait_time_seconds" in payload


# =============================================================================
# ControlCenterAgent Tests
# =============================================================================


def test_control_center_evaluates_threshold():
    """ControlCenterAgent correctly evaluates dispatcher threshold."""
    mock_connector = Mock()
    mock_publisher = Mock()
    
    dispatcher_config = DispatcherConfig(waiting_threshold=250)
    
    agent = ControlCenterAgent(
        dispatcher_config=dispatcher_config,
        mqtt_connector=mock_connector,
        mqtt_publisher=mock_publisher,
        mqtt_base_topic="train_network",
    )
    
    # Below threshold
    assert not agent.evaluate_threshold("Entry Station 1", 200)
    assert not agent.evaluate_threshold("Entry Station 1", 250)  # At threshold, not over
    
    # Above threshold
    assert agent.evaluate_threshold("Entry Station 1", 251)
    assert agent.evaluate_threshold("Entry Station 1", 300)


def test_control_center_requests_extra_train():
    """ControlCenterAgent publishes dispatch request when threshold exceeded."""
    mock_connector = Mock()
    mock_publisher = Mock()
    
    dispatcher_config = DispatcherConfig(waiting_threshold=250)
    
    agent = ControlCenterAgent(
        dispatcher_config=dispatcher_config,
        mqtt_connector=mock_connector,
        mqtt_publisher=mock_publisher,
        mqtt_base_topic="train_network",
    )
    
    # Request extra train
    agent.request_extra_train("Entry Station 1", 275)
    
    # Verify publish
    assert mock_publisher.publish_json.called
    call_args = mock_publisher.publish_json.call_args
    
    # Check topic
    topic = call_args[0][0]
    assert "train_network" in topic
    assert "control_center" in topic or "dispatch" in topic
    
    # Check payload (is JSON string)
    payload_str = call_args[0][1]
    payload = json.loads(payload_str)
    assert "station_name" in payload
    assert payload["station_name"] == "Entry Station 1"
    assert "waiting_count" in payload
    assert payload["waiting_count"] == 275


# =============================================================================
# DispatcherAgent Tests
# =============================================================================


def test_dispatcher_creates_train():
    """DispatcherAgent creates new train with correct configuration."""
    mock_connector = Mock()
    mock_publisher = Mock()
    sample_route = [
        Station("Entry 1", "entry", 55.0, 12.0),
        Station("Exit 1", "exit", 55.1, 12.1, exit_percentage=100),
    ]
    
    train_config = TrainConfig(
        capacity=300,
        departure_interval_minutes=5,
        base_occupancy_percent=16,
    )
    
    agent = DispatcherAgent(
        train_config=train_config,
        route=sample_route,
        mqtt_connector=mock_connector,
        mqtt_publisher=mock_publisher,
        mqtt_base_topic="train_network",
    )
    
    # Create simulation state
    sim_state = SimulationState(current_time=datetime.now())
    
    # Deploy train (returns TrainAgent)
    train_agent = agent.deploy_train(sim_state)
    
    assert train_agent is not None
    assert train_agent.train.capacity == 300
    assert train_agent.train.base_occupancy_count == 48  # 16% of 300
    assert train_agent.train.current_station_index == 0
    assert train_agent.train.current_station_name == "Entry 1"
    assert train_agent.train.id.startswith("train-")


def test_dispatcher_tracks_deployed_trains():
    """DispatcherAgent tracks number of trains deployed."""
    mock_connector = Mock()
    mock_publisher = Mock()
    sample_route = [
        Station("Entry 1", "entry", 55.0, 12.0),
        Station("Exit 1", "exit", 55.1, 12.1, exit_percentage=100),
    ]
    
    train_config = TrainConfig(
        capacity=300,
        departure_interval_minutes=5,
        base_occupancy_percent=16,
    )
    
    agent = DispatcherAgent(
        train_config=train_config,
        route=sample_route,
        mqtt_connector=mock_connector,
        mqtt_publisher=mock_publisher,
    )
    
    # Create simulation state
    sim_state = SimulationState(current_time=datetime.now())
    
    # Deploy multiple trains
    train_agent1 = agent.deploy_train(sim_state)
    train_agent2 = agent.deploy_train(sim_state)
    train_agent3 = agent.deploy_train(sim_state)
    
    # Check unique IDs
    assert train_agent1.train.id != train_agent2.train.id != train_agent3.train.id
    
    # Check simulation state tracking
    assert sim_state.extra_trains_deployed == 3
    assert sim_state.active_train_count == 3
