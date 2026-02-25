# Implementation Plan: Train Capacity Simulation

---

## PHASE 1: Configuration & Infrastructure
*Goal: Set up simulation parameters and data structures*

### 1.1 Extend `config.yaml`
- Add train simulation parameters:
  - Train route stops (Entry1, Entry2, Entry3, Exit1, Exit2)
  - Train capacity (300 passengers)
  - Train departure interval (5 minutes)
  - Passenger arrival rates per time of day (peak: 300/10min, off-peak: 50/10min)
  - Exit percentages (75% at Exit1, 25% at Exit2)
  - Dispatcher threshold (250 waiting passengers)
  - MQTT base topic for train network (e.g., "train_network/")

### 1.2 Add dataclasses to `config.py`
- `TrainConfig`: capacity, route stops, dispatch interval
- `PassengerFlowConfig`: arrival rates by time
- `DispatcherConfig`: threshold for extra trains
- Extend `AppConfig` to include these

### 1.3 Create simulation data models (new file: `src/simulated_city/agents.py`)
- `Train` dataclass: id, capacity, current_location, passengers, status
- `Passenger` dataclass: id, entry_station, exit_station, arrival_time
- `Station` dataclass: name, location (lat/lon), station_type ("entry" or "exit")
- `SimulationState` dataclass: current_time, waiting_passengers, trains_active, etc.

---

## PHASE 2: Core Agent Classes
*Goal: Build reusable agent base classes and MQTT integration*

### 2.1 Create `TrainAgent` class (in `agents.py`)
- Follows route: Entry1 → Entry2 → Entry3 → Exit1 → Exit2
- Methods:
  - `pick_up_passengers(station, available)` → fills to capacity
  - `drop_off_passengers(station)` → removes passengers for that exit
  - `publish_status()` → sends current position, capacity, passengers to MQTT
- Publishes to: `train_network/train/{train_id}/status`
- Runs in async loop, advances position every N seconds

### 2.2 Create `PassengerSourceAgent` class (in `agents.py`)
- Generates passengers at each entry station
- Methods:
  - `generate_passengers(time_of_day)` → returns count based on config
  - `queue_at_station(station_id, count)` → adds to waiting queue
  - `publish_arrival()` → notifies control center of arrival
- Publishes to: `train_network/station/{station_id}/passengers/waiting`

### 2.3 Create `SensorAgent` class (in `agents.py`)
- Monitors each station platform
- Methods:
  - `count_waiting(station_id)` → returns waiting passenger count
  - `publish_observation()` → sensor data to control center
- Publishes to: `train_network/station/{station_id}/sensor/waiting_count`

### 2.4 Create `ControlCenterAgent` class (in `agents.py`)
- Subscribes to sensor data
- Methods:
  - `evaluate_threshold(station_id, waiting_count)` → checks if >250
  - `request_extra_train(route)` → triggers dispatcher
- Subscribes to: `train_network/station/+/sensor/waiting_count`
- Publishes to: `train_network/control_center/dispatch_request`

### 2.5 Create `DispatcherAgent` class (in `agents.py`)
- Subscribes to dispatch requests
- Methods:
  - `deploy_train()` → creates new train instance
  - `manage_fleet()` → schedules outbound trains
- Subscribes to: `train_network/control_center/dispatch_request`

---

## PHASE 3: Testing & Validation
*Goal: Verify core logic before notebooks*

### 3.1 Add unit tests (`tests/test_agents.py`)
- Test train picks up/drops off passengers correctly
- Test passenger generation rates match config
- Test dispatcher threshold logic
- Test MQTT message structure

### 3.2 Add smoke test (`tests/test_train_simulation.py`)
- End-to-end: run all agents for 10 simulated minutes
- Verify MQTT messages are published
- Verify passenger counts decrease at exits

---

## PHASE 4: Exercise Notebooks
*Goal: Guide students to build the simulation themselves*

### 4.1 Notebook: `05_train_network_basics.ipynb`
- Load train config from `config.yaml`
- Manually create a single train object
- Manually simulate one route cycle
- Publish train position to MQTT

### 4.2 Notebook: `05_train_passenger_source.ipynb`
- Create passenger source agent
- Simulate passenger arrivals over peaks (18:00, 19:00, 20:00)
- Publish waiting passenger counts
- Visualize on map

### 4.3 Notebook: `05_train_control_center.ipynb`
- Implement control center logic
- Subscribe to sensor data
- Trigger dispatcher when threshold exceeded
- Log dispatch decisions

### 4.4 Notebook: `05_train_full_simulation.ipynb`
- Orchestrate all agents together
- Run 30+ simulated minutes
- Visualize:
  - Train positions on map
  - Passenger queues per station
  - Dispatcher trigger events
  - Performance metrics (avg wait time, trains deployed, etc.)

---

## PHASE 5: Visualization & Monitoring
*Goal: Create live dashboard for simulation*

### 5.1 Enhanced map viewer (new notebook: `05_train_map_viewer.ipynb`)
- Visualize train positions (different colors)
- Show passenger queue size as circle overlay on each station
- Color-code entry vs exit stations
- Display train capacity as percentage

### 5.2 Real-time metrics dashboard (new notebook: `05_train_dashboard.ipynb`)
- Plot waiting passengers over time per station
- Plot trains deployed over time
- Track throughput (passengers handled per 10min)
- Compare vs expected capacity

---

## PHASE 6: Documentation & Exercises
*Goal: Add learning materials*

### 6.1 New doc: `docs/train_simulation.md`
- Explain train network architecture
- Walk through each agent's responsibility
- Show expected MQTT message formats
- Provide exercise prompts

### 6.2 Exercises in `docs/exercises.md`
- Ex 1: Modify train capacity, re-run, observe effect
- Ex 2: Change passenger arrival rates, observe queue growth
- Ex 3: Adjust dispatcher threshold, compare extra trains deployed
- Ex 4: Add weather impact (trains delayed if storm)

---

## TIMELINE & DEPENDENCIES

```
Phase 1 (Config & Models)
  ├─ 1.1 Update config.yaml
  ├─ 1.2 Extend config.py dataclasses
  └─ 1.3 Create agents.py with data models
       ↓
Phase 2 (Agent Classes)
  ├─ 2.1 TrainAgent
  ├─ 2.2 PassengerSourceAgent
  ├─ 2.3 SensorAgent
  ├─ 2.4 ControlCenterAgent
  └─ 2.5 DispatcherAgent
       ↓
Phase 3 (Testing)
  ├─ 3.1 Unit tests
  └─ 3.2 Smoke test
       ↓
Phase 4 (Notebooks) — Can run in parallel
  ├─ 4.1 Basics
  ├─ 4.2 Passenger Source
  ├─ 4.3 Control Center
  └─ 4.4 Full Simulation
       ↓
Phase 5 (Visualization)
  ├─ 5.1 Map Viewer
  └─ 5.2 Dashboard
       ↓
Phase 6 (Documentation)
  ├─ 6.1 train_simulation.md
  └─ 6.2 exercises.md
```

---

## NOTES FOR REFINEMENT

- **Naming conventions**: Follow existing project patterns (dataclass convention, snake_case for methods)
- **MQTT topic structure**: Use `train_network/` base to isolate from other simulations
- **Async patterns**: Use `asyncio` for agent loops (consistent with existing notebooks)
- **Config validation**: Extend config.py to validate train route stops exist
- **Message format**: Standardize JSON payloads (include timestamp, agent_id, etc.)
- **Beginner-friendly**: Add helpful comments explaining **why** not just **what**
- **Testing-first approach**: Write simple test before each agent implementation
