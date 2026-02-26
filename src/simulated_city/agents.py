"""Data models and agent classes for train network simulation.

This module provides dataclasses for representing trains, passengers, stations,
and simulation state. These models form the foundation for agent-based simulation
of train capacity management.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Literal


class TrainStatus(Enum):
    """Current operational status of a train."""
    IDLE = "idle"
    IN_TRANSIT = "in_transit"
    AT_STATION = "at_station"
    BOARDING = "boarding"
    ALIGHTING = "alighting"


@dataclass
class Station:
    """Represents a station in the train network.
    
    Stations are either entry points (where passengers board) or exit points
    (where passengers alight). Exit stations specify what percentage of
    passengers leave at that stop.
    """
    name: str
    station_type: Literal["entry", "exit"]
    location_lat: float
    location_lon: float
    exit_percentage: int | None = None  # Only for exit stations
    
    def __post_init__(self):
        """Validate station configuration."""
        if self.station_type == "exit" and self.exit_percentage is None:
            raise ValueError(f"Exit station '{self.name}' must have exit_percentage")
        if self.station_type == "entry" and self.exit_percentage is not None:
            raise ValueError(f"Entry station '{self.name}' should not have exit_percentage")


@dataclass
class Passenger:
    """Represents a single passenger in the simulation.
    
    Each passenger has an entry station where they board and an exit station
    where they will alight. The arrival_time tracks when they entered the system.
    """
    id: str
    entry_station: str
    exit_station: str
    arrival_time: datetime
    boarding_time: datetime | None = None  # When they boarded a train
    
    @property
    def waiting_duration_seconds(self) -> float:
        """Calculate how long this passenger has been waiting."""
        if self.boarding_time is None:
            return (datetime.now() - self.arrival_time).total_seconds()
        return (self.boarding_time - self.arrival_time).total_seconds()


@dataclass
class Train:
    """Represents a train operating in the network.
    
    Trains follow a fixed route, pick up passengers at entry stations, and
    drop off passengers at exit stations according to the exit percentages.
    Base occupancy represents non-event passengers already on the train.
    """
    id: str
    capacity: int
    current_station_index: int  # Index in the route list
    current_station_name: str
    passengers_onboard: list[Passenger] = field(default_factory=list)
    status: TrainStatus = TrainStatus.IDLE
    base_occupancy_count: int = 0  # Non-event passengers (constant load)
    
    @property
    def total_passengers(self) -> int:
        """Total passengers including base occupancy and event passengers."""
        return len(self.passengers_onboard) + self.base_occupancy_count
    
    @property
    def available_capacity(self) -> int:
        """How many more passengers can board."""
        return max(0, self.capacity - self.total_passengers)
    
    @property
    def capacity_percentage(self) -> float:
        """Current capacity utilization as percentage."""
        return (self.total_passengers / self.capacity) * 100 if self.capacity > 0 else 0.0
    
    @property
    def is_full(self) -> bool:
        """Check if train is at capacity."""
        return self.total_passengers >= self.capacity


@dataclass
class StationQueue:
    """Tracks passengers waiting at a specific station.
    
    This represents the platform queue state at a station, used by sensors
    and the control center to determine if extra trains are needed.
    """
    station_name: str
    waiting_passengers: list[Passenger] = field(default_factory=list)
    
    @property
    def count(self) -> int:
        """Number of passengers waiting."""
        return len(self.waiting_passengers)
    
    @property
    def average_wait_time_seconds(self) -> float:
        """Calculate average wait time for passengers in queue."""
        if not self.waiting_passengers:
            return 0.0
        total_wait = sum(p.waiting_duration_seconds for p in self.waiting_passengers)
        return total_wait / len(self.waiting_passengers)
    
    def add_passengers(self, passengers: list[Passenger]) -> None:
        """Add new passengers to the waiting queue."""
        self.waiting_passengers.extend(passengers)
    
    def remove_passengers(self, count: int) -> list[Passenger]:
        """Remove and return up to 'count' passengers from queue (FIFO)."""
        if count <= 0:
            return []
        
        removed = self.waiting_passengers[:count]
        self.waiting_passengers = self.waiting_passengers[count:]
        return removed


@dataclass
class SimulationState:
    """Overall state of the simulation at a given moment.
    
    This tracks the current simulation time, all active trains, station queues,
    and metrics for monitoring and analysis.
    """
    current_time: datetime
    trains: dict[str, Train] = field(default_factory=dict)  # train_id -> Train
    station_queues: dict[str, StationQueue] = field(default_factory=dict)  # station_name -> StationQueue
    total_passengers_generated: int = 0
    total_passengers_boarded: int = 0
    total_passengers_alighted: int = 0
    extra_trains_deployed: int = 0
    
    @property
    def active_train_count(self) -> int:
        """Number of trains currently in the system."""
        return len(self.trains)
    
    @property
    def total_waiting_passengers(self) -> int:
        """Sum of all passengers waiting across all stations."""
        return sum(queue.count for queue in self.station_queues.values())
    
    @property
    def average_train_capacity(self) -> float:
        """Average capacity utilization across all trains."""
        if not self.trains:
            return 0.0
        total_capacity = sum(train.capacity_percentage for train in self.trains.values())
        return total_capacity / len(self.trains)
    
    def get_station_queue(self, station_name: str) -> StationQueue:
        """Get or create a station queue."""
        if station_name not in self.station_queues:
            self.station_queues[station_name] = StationQueue(station_name=station_name)
        return self.station_queues[station_name]
    
    def add_train(self, train: Train) -> None:
        """Register a new train in the simulation."""
        self.trains[train.id] = train
    
    def remove_train(self, train_id: str) -> Train | None:
        """Remove a train from the simulation (e.g., completed route)."""
        return self.trains.pop(train_id, None)


# =============================================================================
# Agent Classes (Phase 2)
# =============================================================================


class TrainAgent:
    """Agent that manages a single train's movement and passenger operations.
    
    The train follows a fixed route, picking up passengers at entry stations
    and dropping them off at exit stations. It publishes status updates via MQTT.
    """
    
    def __init__(
        self,
        train: Train,
        route: list[Station],
        mqtt_publisher,
        mqtt_base_topic: str = "train_network",
    ):
        """Initialize a train agent.
        
        Args:
            train: The Train data model to manage
            route: List of stations in order (entry stations, then exit stations)
            mqtt_publisher: MqttPublisher instance for publishing updates
            mqtt_base_topic: Base MQTT topic for all train network messages
        """
        self.train = train
        self.route = route
        self.mqtt_publisher = mqtt_publisher
        self.mqtt_base_topic = mqtt_base_topic
        self._running = False
    
    def pick_up_passengers(self, station_queue: StationQueue) -> int:
        """Pick up passengers from station queue up to available capacity.
        
        Returns:
            Number of passengers that boarded
        """
        available = self.train.available_capacity
        if available <= 0:
            return 0
        
        # Remove passengers from queue (FIFO) and add to train
        boarded_passengers = station_queue.remove_passengers(available)
        for passenger in boarded_passengers:
            passenger.boarding_time = datetime.now()
        
        self.train.passengers_onboard.extend(boarded_passengers)
        return len(boarded_passengers)
    
    def drop_off_passengers(self, station: Station) -> int:
        """Drop off passengers at an exit station based on exit percentage.
        
        Returns:
            Number of passengers that alighted
        """
        if station.station_type != "exit" or station.exit_percentage is None:
            return 0
        
        # Calculate how many passengers exit here
        passengers_to_exit = []
        remaining_passengers = []
        
        for passenger in self.train.passengers_onboard:
            if passenger.exit_station == station.name:
                passengers_to_exit.append(passenger)
            else:
                remaining_passengers.append(passenger)
        
        # If this is a designated exit station, also use exit percentage
        # (Some passengers may exit even if it's not their target station)
        current_count = len(self.train.passengers_onboard)
        exit_count = int(current_count * station.exit_percentage / 100)
        
        # Use the maximum of targeted exits or percentage-based exits
        if len(passengers_to_exit) < exit_count:
            # Need to remove more passengers to meet percentage
            additional_needed = exit_count - len(passengers_to_exit)
            if additional_needed > 0 and remaining_passengers:
                # Take additional passengers from remaining (FIFO)
                additional = remaining_passengers[:additional_needed]
                passengers_to_exit.extend(additional)
                remaining_passengers = remaining_passengers[additional_needed:]
        
        self.train.passengers_onboard = remaining_passengers
        return len(passengers_to_exit)
    
    def publish_status(self) -> None:
        """Publish current train status to MQTT."""
        import json
        
        station = self.route[self.train.current_station_index]
        
        payload = {
            "train_id": self.train.id,
            "status": self.train.status.value,
            "station_name": self.train.current_station_name,
            "station_index": self.train.current_station_index,
            "station_lat": station.location_lat,
            "station_lon": station.location_lon,
            "passengers_onboard": len(self.train.passengers_onboard),
            "base_occupancy": self.train.base_occupancy_count,
            "total_passengers": self.train.total_passengers,
            "capacity": self.train.capacity,
            "capacity_percentage": round(self.train.capacity_percentage, 1),
            "available_capacity": self.train.available_capacity,
            "timestamp": datetime.now().isoformat(),
        }
        
        topic = f"{self.mqtt_base_topic}/train/{self.train.id}/status"
        self.mqtt_publisher.publish_json(topic, json.dumps(payload), qos=0)
    
    async def run(self, simulation_state: SimulationState, travel_time_seconds: float = 30) -> None:
        """Run the train agent's main loop.
        
        Args:
            simulation_state: Global simulation state (for accessing station queues)
            travel_time_seconds: Time to wait between stations
        """
        import asyncio
        
        self._running = True
        
        while self._running and self.train.current_station_index < len(self.route):
            station = self.route[self.train.current_station_index]
            self.train.current_station_name = station.name
            self.train.status = TrainStatus.AT_STATION
            
            # Publish arrival at station
            self.publish_status()
            
            # Handle passenger operations based on station type
            if station.station_type == "entry":
                # Pick up passengers
                self.train.status = TrainStatus.BOARDING
                queue = simulation_state.get_station_queue(station.name)
                boarded = self.pick_up_passengers(queue)
                simulation_state.total_passengers_boarded += boarded
                
            elif station.station_type == "exit":
                # Drop off passengers
                self.train.status = TrainStatus.ALIGHTING
                alighted = self.drop_off_passengers(station)
                simulation_state.total_passengers_alighted += alighted
            
            # Publish status after operations
            self.publish_status()
            
            # Move to next station
            self.train.current_station_index += 1
            
            if self.train.current_station_index < len(self.route):
                self.train.status = TrainStatus.IN_TRANSIT
                self.publish_status()
                await asyncio.sleep(travel_time_seconds)
        
        # Train completed route
        self.train.status = TrainStatus.IDLE
        self.publish_status()
        self._running = False
    
    def stop(self) -> None:
        """Stop the train agent."""
        self._running = False


class PassengerSourceAgent:
    """Agent that generates passengers at entry stations based on time of day.
    
    This agent simulates passenger arrivals according to configured peak/off-peak rates.
    """
    
    def __init__(
        self,
        station: Station,
        exit_stations: list[Station],
        passenger_flow_config,
        mqtt_publisher,
        mqtt_base_topic: str = "train_network",
    ):
        """Initialize passenger source agent.
        
        Args:
            station: Entry station where passengers arrive
            exit_stations: List of possible exit stations for passengers
            passenger_flow_config: PassengerFlowConfig with arrival rates
            mqtt_publisher: MqttPublisher instance
            mqtt_base_topic: Base MQTT topic
        """
        self.station = station
        self.exit_stations = exit_stations
        self.passenger_flow_config = passenger_flow_config
        self.mqtt_publisher = mqtt_publisher
        self.mqtt_base_topic = mqtt_base_topic
        self._running = False
        self._passenger_counter = 0
    
    def get_arrival_rate(self, current_hour: int) -> int:
        """Get passenger arrival rate for the given hour.
        
        Returns:
            Passengers per 10 minutes for this hour
        """
        # Check if current hour is in peak hours
        for peak_config in self.passenger_flow_config.peak_hours:
            if peak_config.start <= current_hour <= peak_config.end:
                return peak_config.passengers_per_10min
        
        # Use off-peak rate
        return self.passenger_flow_config.off_peak_passengers_per_10min
    
    def generate_passengers(self, count: int) -> list[Passenger]:
        """Generate a batch of passengers.
        
        Args:
            count: Number of passengers to generate
            
        Returns:
            List of newly generated passengers
        """
        import random
        
        passengers = []
        for _ in range(count):
            self._passenger_counter += 1
            passenger_id = f"{self.station.name}-p{self._passenger_counter}"
            
            # Randomly assign an exit station
            exit_station = random.choice(self.exit_stations)
            
            passenger = Passenger(
                id=passenger_id,
                entry_station=self.station.name,
                exit_station=exit_station.name,
                arrival_time=datetime.now(),
            )
            passengers.append(passenger)
        
        return passengers
    
    def publish_arrival(self, passenger_count: int, queue_size: int) -> None:
        """Publish passenger arrival event to MQTT."""
        import json
        
        payload = {
            "station_name": self.station.name,
            "new_arrivals": passenger_count,
            "queue_size": queue_size,
            "timestamp": datetime.now().isoformat(),
        }
        
        topic = f"{self.mqtt_base_topic}/station/{self.station.name}/passengers/arrivals"
        self.mqtt_publisher.publish_json(topic, json.dumps(payload), qos=0)
    
    async def run(self, simulation_state: SimulationState, interval_seconds: float = 60) -> None:
        """Run the passenger source agent's main loop.
        
        Args:
            simulation_state: Global simulation state
            interval_seconds: How often to generate passengers (default: 60s = 1 minute)
        """
        import asyncio
        
        self._running = True
        
        while self._running:
            current_time = simulation_state.current_time
            current_hour = current_time.hour
            
            # Get arrival rate for current hour (passengers per 10 minutes)
            rate_per_10min = self.get_arrival_rate(current_hour)
            
            # Convert to rate per interval
            # If interval is 60s (1 min), we get 1/10th of 10-minute rate
            passengers_this_interval = int(rate_per_10min * (interval_seconds / 600))
            
            if passengers_this_interval > 0:
                # Generate passengers
                new_passengers = self.generate_passengers(passengers_this_interval)
                
                # Add to station queue
                queue = simulation_state.get_station_queue(self.station.name)
                queue.add_passengers(new_passengers)
                
                # Update simulation stats
                simulation_state.total_passengers_generated += len(new_passengers)
                
                # Publish arrival event
                self.publish_arrival(len(new_passengers), queue.count)
            
            await asyncio.sleep(interval_seconds)
    
    def stop(self) -> None:
        """Stop the passenger source agent."""
        self._running = False


class SensorAgent:
    """Agent that monitors a station platform and publishes passenger counts.
    
    Sensors provide real-time data to the control center for dispatch decisions.
    """
    
    def __init__(
        self,
        station: Station,
        mqtt_publisher,
        mqtt_base_topic: str = "train_network",
    ):
        """Initialize sensor agent.
        
        Args:
            station: Station to monitor
            mqtt_publisher: MqttPublisher instance
            mqtt_base_topic: Base MQTT topic
        """
        self.station = station
        self.mqtt_publisher = mqtt_publisher
        self.mqtt_base_topic = mqtt_base_topic
        self._running = False
    
    def count_waiting(self, station_queue: StationQueue) -> int:
        """Count passengers waiting at the station.
        
        Returns:
            Number of waiting passengers
        """
        return station_queue.count
    
    def publish_observation(self, waiting_count: int, avg_wait_time: float) -> None:
        """Publish sensor observation to MQTT."""
        import json
        
        payload = {
            "station_name": self.station.name,
            "waiting_count": waiting_count,
            "avg_wait_time_seconds": round(avg_wait_time, 1),
            "timestamp": datetime.now().isoformat(),
        }
        
        topic = f"{self.mqtt_base_topic}/station/{self.station.name}/sensor/waiting_count"
        self.mqtt_publisher.publish_json(topic, json.dumps(payload), qos=0)
    
    async def run(self, simulation_state: SimulationState, interval_seconds: float = 10) -> None:
        """Run the sensor agent's main loop.
        
        Args:
            simulation_state: Global simulation state
            interval_seconds: How often to publish observations (default: 10s)
        """
        import asyncio
        
        self._running = True
        
        while self._running:
            queue = simulation_state.get_station_queue(self.station.name)
            waiting_count = self.count_waiting(queue)
            avg_wait_time = queue.average_wait_time_seconds
            
            self.publish_observation(waiting_count, avg_wait_time)
            
            await asyncio.sleep(interval_seconds)
    
    def stop(self) -> None:
        """Stop the sensor agent."""
        self._running = False


class ControlCenterAgent:
    """Agent that monitors sensor data and triggers dispatcher when needed.
    
    The control center subscribes to sensor data and makes decisions about
    deploying extra trains based on configured thresholds.
    """
    
    def __init__(
        self,
        dispatcher_config,
        mqtt_connector,
        mqtt_publisher,
        mqtt_base_topic: str = "train_network",
    ):
        """Initialize control center agent.
        
        Args:
            dispatcher_config: DispatcherConfig with threshold settings
            mqtt_connector: MqttConnector instance for subscribing
            mqtt_publisher: MqttPublisher instance for publishing decisions
            mqtt_base_topic: Base MQTT topic
        """
        self.dispatcher_config = dispatcher_config
        self.mqtt_connector = mqtt_connector
        self.mqtt_publisher = mqtt_publisher
        self.mqtt_base_topic = mqtt_base_topic
        self._running = False
        self._last_dispatch_time = {}  # station_name -> last dispatch time
    
    def evaluate_threshold(self, station_name: str, waiting_count: int) -> bool:
        """Check if waiting count exceeds threshold.
        
        Args:
            station_name: Name of the station
            waiting_count: Current number of waiting passengers
            
        Returns:
            True if extra train should be deployed
        """
        if waiting_count <= self.dispatcher_config.waiting_threshold:
            return False
        
        # Prevent rapid repeated dispatches for same station
        # Wait at least 5 minutes between dispatches for same station
        now = datetime.now()
        if station_name in self._last_dispatch_time:
            time_since_last = (now - self._last_dispatch_time[station_name]).total_seconds()
            if time_since_last < 300:  # 5 minutes
                return False
        
        return True
    
    def request_extra_train(self, station_name: str, waiting_count: int) -> None:
        """Publish request for extra train to dispatcher.
        
        Args:
            station_name: Station where extra capacity is needed
            waiting_count: Current number of waiting passengers
        """
        import json
        
        payload = {
            "station_name": station_name,
            "waiting_count": waiting_count,
            "threshold": self.dispatcher_config.waiting_threshold,
            "timestamp": datetime.now().isoformat(),
        }
        
        topic = f"{self.mqtt_base_topic}/control_center/dispatch_request"
        self.mqtt_publisher.publish_json(topic, json.dumps(payload), qos=0)
        
        # Record dispatch time
        self._last_dispatch_time[station_name] = datetime.now()
    
    def on_sensor_message(self, client, userdata, message) -> None:
        """Callback for sensor data messages.
        
        Args:
            client: MQTT client
            userdata: User data
            message: MQTT message containing sensor data
        """
        import json
        
        try:
            data = json.loads(message.payload.decode())
            station_name = data.get("station_name")
            waiting_count = data.get("waiting_count", 0)
            
            if self.evaluate_threshold(station_name, waiting_count):
                self.request_extra_train(station_name, waiting_count)
        
        except (json.JSONDecodeError, KeyError) as e:
            # Log error but don't crash
            pass
    
    def start(self) -> None:
        """Start the control center agent (subscribe to sensor topics)."""
        self._running = True
        
        # Subscribe to all sensor waiting_count topics
        subscribe_topic = f"{self.mqtt_base_topic}/station/+/sensor/waiting_count"
        self.mqtt_connector.client.subscribe(subscribe_topic, qos=0)
        self.mqtt_connector.client.message_callback_add(subscribe_topic, self.on_sensor_message)
    
    def stop(self) -> None:
        """Stop the control center agent."""
        self._running = False
        
        # Unsubscribe from sensor topics
        subscribe_topic = f"{self.mqtt_base_topic}/station/+/sensor/waiting_count"
        self.mqtt_connector.client.unsubscribe(subscribe_topic)


class DispatcherAgent:
    """Agent that deploys extra trains in response to control center requests.
    
    The dispatcher manages the train fleet and creates new trains when needed.
    """
    
    def __init__(
        self,
        train_config,
        route: list[Station],
        mqtt_connector,
        mqtt_publisher,
        mqtt_base_topic: str = "train_network",
    ):
        """Initialize dispatcher agent.
        
        Args:
            train_config: TrainConfig with train specifications
            route: List of stations that trains follow
            mqtt_connector: MqttConnector instance for subscribing
            mqtt_publisher: MqttPublisher instance for publishing
            mqtt_base_topic: Base MQTT topic
        """
        self.train_config = train_config
        self.route = route
        self.mqtt_connector = mqtt_connector
        self.mqtt_publisher = mqtt_publisher
        self.mqtt_base_topic = mqtt_base_topic
        self._running = False
        self._train_counter = 0
        self._deployed_trains = {}  # train_id -> TrainAgent
    
    def deploy_train(self, simulation_state: SimulationState) -> TrainAgent:
        """Create and deploy a new train.
        
        Args:
            simulation_state: Global simulation state
            
        Returns:
            Newly created TrainAgent
        """
        self._train_counter += 1
        train_id = f"train-extra-{self._train_counter}"
        
        # Calculate base occupancy count (16% of capacity)
        base_occupancy = int(self.train_config.capacity * self.train_config.base_occupancy_percent / 100)
        
        train = Train(
            id=train_id,
            capacity=self.train_config.capacity,
            current_station_index=0,
            current_station_name=self.route[0].name,
            base_occupancy_count=base_occupancy,
            status=TrainStatus.IDLE,
        )
        
        # Add train to simulation
        simulation_state.add_train(train)
        simulation_state.extra_trains_deployed += 1
        
        # Create train agent
        train_agent = TrainAgent(
            train=train,
            route=self.route,
            mqtt_publisher=self.mqtt_publisher,
            mqtt_base_topic=self.mqtt_base_topic,
        )
        
        self._deployed_trains[train_id] = train_agent
        
        return train_agent
    
    def on_dispatch_request(self, client, userdata, message) -> None:
        """Callback for dispatch request messages from control center.
        
        Args:
            client: MQTT client
            userdata: User data (should contain simulation_state)
            message: MQTT message containing dispatch request
        """
        import json
        
        try:
            data = json.loads(message.payload.decode())
            station_name = data.get("station_name")
            waiting_count = data.get("waiting_count")
            
            # Get simulation state from userdata
            simulation_state = userdata.get("simulation_state")
            if simulation_state is None:
                return
            
            # Deploy extra train
            train_agent = self.deploy_train(simulation_state)
            
            # Publish deployment confirmation
            payload = {
                "train_id": train_agent.train.id,
                "station_name": station_name,
                "waiting_count": waiting_count,
                "timestamp": datetime.now().isoformat(),
            }
            topic = f"{self.mqtt_base_topic}/dispatcher/train_deployed"
            self.mqtt_publisher.publish_json(topic, json.dumps(payload), qos=0)
            
            # Start the train agent asynchronously (needs to be done in async context)
            # The train will be started by the main simulation loop
        
        except (json.JSONDecodeError, KeyError) as e:
            # Log error but don't crash
            pass
    
    def start(self, simulation_state: SimulationState) -> None:
        """Start the dispatcher agent (subscribe to dispatch requests).
        
        Args:
            simulation_state: Global simulation state to pass to callbacks
        """
        self._running = True
        
        # Set up userdata with simulation state
        self.mqtt_connector.client.user_data_set({"simulation_state": simulation_state})
        
        # Subscribe to dispatch request topic
        subscribe_topic = f"{self.mqtt_base_topic}/control_center/dispatch_request"
        self.mqtt_connector.client.subscribe(subscribe_topic, qos=1)
        self.mqtt_connector.client.message_callback_add(subscribe_topic, self.on_dispatch_request)
    
    def stop(self) -> None:
        """Stop the dispatcher agent."""
        self._running = False
        
        # Stop all deployed train agents
        for train_agent in self._deployed_trains.values():
            train_agent.stop()
        
        # Unsubscribe from dispatch requests
        subscribe_topic = f"{self.mqtt_base_topic}/control_center/dispatch_request"
        self.mqtt_connector.client.unsubscribe(subscribe_topic)
    
    def get_deployed_trains(self) -> dict[str, TrainAgent]:
        """Get dictionary of all deployed extra trains.
        
        Returns:
            Dictionary mapping train_id to TrainAgent
        """
        return self._deployed_trains
