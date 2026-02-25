# Simulated City Workshop: Train Capacity Simulator

A beginner-friendly workshop for learning agent-based programming in Python. You build a train station simulation that manages passenger flow during high-demand events (like football matches).

## Quick Start

1. **Setup**: Read [docs/setup.md](docs/setup.md) to install dependencies.
2. **Learn the basics**: Read [docs/overview.md](docs/overview.md) for an overview of the library.
3. **Explore notebooks**: Start with the notebooks in `notebooks/` to understand the simulation.

## About This Simulation

This model simulates train capacity management at a station during peak demand periods. You learn how **agents** (passengers), **sensors** (platform counters), and **controllers** (train dispatch logic) work together.

### The Four Components

#### 1. The Trigger: Passengers and Trains

**Train Network Route:**
The train follows a fixed route with five stops in this order:
1. Entry Station 1 (pick up passengers)
2. Entry Station 2 (pick up passengers)
3. Entry Station 3 (pick up passengers)
4. Exit Station 1 (drop off 75% of passengers)
5. Exit Station 2 (drop off remaining 25% of passengers)

A new train departs every 5 minutes and follows this same route.

**Passengers (Agents):**
- Three entry stations feed passengers into the network
- At 19:00 (peak time): 300 passengers arrive every 10 minutes
- At 18:00 and 20:00: 150 passengers arrive every 10 minutes  
- Off-peak hours: 50 passengers arrive every 10 minutes
- At exit station 1: 75% of passengers leave the train
- At exit station 2: remaining 25% of passengers leave the train

**Trains:**
- A train arrives at the first entry station every 5 minutes
- Each train holds a maximum of 300 passengers
- Base occupancy (non-event passengers): 16% capacity
- Trains only pick up passengers at the three entry stations
- Trains only drop off passengers at the two exit stations

#### 2. Sensors: Platform Monitoring

- Each station platform has sensors that count waiting passengers
- Sensors report the number of people waiting every minute
- This data feeds into the control center

#### 3. The Control Center: The Logic

The train control center monitors real-time data:
- Tracks the number of waiting passengers
- Decision rule: If waiting passengers exceed 250, assign an extra train to that trip
- Allocates additional trains as needed during peak demand

#### 4. The Response: Train Dispatch

The controller (dispatcher) responds to control center decisions:
- Deploys extra trains when passenger counts trigger the threshold
- Updates train schedules in real time
- Manages the flow of passengers through the network

## How the Simulation Works

### Agent-Based Architecture

Each component (passengers, trains, sensors, dispatcher) operates as an **independent agent**:
- Agents make decisions based on their own logic and current state
- Agents communicate through MQTT messages (see below)
- Agents run in parallel and react to events asynchronously
- You extend the simulation by creating new agents or modifying existing ones

### Communication: MQTT Messaging

Agents communicate through **MQTT pub/sub messaging**:
- **Passengers** publish arrival events (I arrived at platform X at time Y)
- **Trains** publish position and capacity updates (I am at station Z with N passengers)
- **Sensors** publish observations (Platform X has N waiting passengers)
- **Control Center** publishes dispatch decisions (Assign extra train to route A)
- **Dispatcher** subscribes to control center decisions and executes them

The library provides helpers in `simulated_city.mqtt` to simplify publishing and subscribing.

### Configuration

Simulation parameters are controlled through two files:
- **`config.yaml`** — Non-secret settings (MQTT broker host, port, base topic, passenger arrival rates, train capacity, decision rules)
- **`.env`** — Secrets like MQTT credentials (kept out of version control)

Edit `config.yaml` to change simulation behavior without modifying code.

## Running the Simulation

**Start your environment:**
```bash
source .venv/bin/activate
```

**Run in a notebook (recommended for learning):**
```bash
python -m jupyterlab
```
Open a notebook in `notebooks/` and follow the exercises.

**Run a demo script:**
```bash
python scripts/demo/01_config_and_mqtt.py
```

**Run tests:**
```bash
python -m pytest
```

## Learning Path

1. **Python fundamentals**: `notebooks/00_python_fundamentals.ipynb`
2. **Simulated City basics**: `notebooks/01_simulated_city_basics.ipynb`
3. **Mapping with MapLibre**: `notebooks/02_maplibre_city_hall_random_walk.ipynb`
4. **MQTT and real-time agents**: `notebooks/03_mqtt_random_walk/`
5. **Advanced agents and weather**: `notebooks/04_advanced_random_walk/`

---

## Project Structure

- `src/simulated_city/` — the library modules you import
- `notebooks/` — workshop exercises and interactive examples
- `docs/` — handouts, setup guides, and exercise descriptions
- `tests/` — basic sanity checks
- `scripts/demo/` — example simulations you can run

## Next Steps

- Read [docs/setup.md](docs/setup.md) to set up your environment
- Open `notebooks/00_python_fundamentals.ipynb` to start learning
- Check `docs/exercises.md` for hands-on tasks