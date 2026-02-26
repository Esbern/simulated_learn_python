# Train Network Simulation Exercises

This document contains hands-on exercises for exploring and extending the train network simulation. Each exercise builds your understanding of agent-based systems, MQTT communication, and capacity planning.

---

## Prerequisites

Before starting these exercises:
1. Complete notebooks `00_python_fundamentals.ipynb` and `01_simulated_city_basics.ipynb`
2. Read [docs/train_simulation.md](train_simulation.md) for system architecture
3. Ensure MQTT broker is running: `mosquitto`
4. Have notebooks open: `notebooks/05_train_*.ipynb`

---

## Exercise 1: Modify Train Capacity

**Goal**: Understand how train capacity affects passenger throughput and queue sizes.

**Background**: The default train capacity is 180 passengers. During peak hours (300 passengers arriving per 10 minutes), trains may struggle to handle demand. By changing capacity, you can observe how system performance changes.

### Steps

1. **Baseline measurement**:
   - Open `notebooks/05_train_full_simulation.ipynb`
   - Run the full simulation (30 minutes)
   - Record these metrics:
     - Total passengers boarded: ___________
     - Total passengers alighted: ___________
     - Peak queue size: ___________
     - Average waiting time: ___________
     - Extra trains deployed: ___________

2. **Increase capacity**:
   - Open `config.yaml`
   - Change `train_config.capacity` from `180` to `220` (22% increase)
   - Restart the notebook kernel
   - Re-run the simulation
   - Record the same metrics above

3. **Extreme capacity test**:
   - Change capacity to `300` (67% increase)
   - Re-run and record metrics

4. **Low capacity stress test**:
   - Change capacity to `120` (33% decrease)
   - Re-run and record metrics

### Analysis Questions

1. **How does increasing capacity affect queue sizes?**
   - At capacity 220: _______________________________
   - At capacity 300: _______________________________
   
2. **Does higher capacity reduce extra trains deployed?**
   - Expected: yes/no because ________________________
   - Observed: yes/no

3. **What is the minimum capacity needed to handle peak demand (300 pax/10min) without exceeding the threshold (250)?**
   - Calculation: _______________________________
   - Test result: _______________________________

4. **What are the trade-offs of very high capacity trains?**
   - Benefits: _______________________________
   - Drawbacks: _______________________________

### Expected Observations

- **Higher capacity** → Fewer trains needed, lower peak queues, better throughput
- **Lower capacity** → More extra trains deployed, higher peak queues, possible bottlenecks
- **Optimal capacity** balances cost (fewer trains) with service quality (shorter waits)

### Extension

Try non-uniform capacity:
- Modify `TrainAgent` to have some trains with different capacities
- Simulate "express" trains (capacity 240) vs "local" trains (capacity 150)
- Compare mixed-fleet performance vs uniform fleet

---

## Exercise 2: Change Passenger Arrival Rates

**Goal**: Explore how different demand patterns affect network load and required capacity.

**Background**: The current configuration models a football match with peak arrival at 18:00-19:00 (300 pax/10min). Different events have different arrival patterns. You'll simulate various scenarios.

### Steps

1. **Current scenario** (football match):
   - Peak: 18:00-19:00 at 300 pax/10min
   - Shoulders: 17:00-18:00 and 19:00-20:00 at 150 pax/10min
   - Off-peak: 50 pax/10min
   - Run simulation, record: peak queue _____, extra trains _____

2. **Scenario A: Concert** (longer peak):
   Open `config.yaml` and modify `passenger_flow.peak_hours`:
   ```yaml
   peak_hours:
     - start: 17
       end: 18
       passengers_per_10min: 200
     - start: 18
       end: 19
       passengers_per_10min: 250
     - start: 19
       end: 20
       passengers_per_10min: 250
     - start: 20
       end: 21
       passengers_per_10min: 200
   ```
   Run simulation, record metrics.

3. **Scenario B: Multiple events** (double peak):
   ```yaml
   peak_hours:
     - start: 17
       end: 18
       passengers_per_10min: 250
     - start: 18
       end: 19
       passengers_per_10min: 100
     - start: 19
       end: 20
       passengers_per_10min: 250
   ```
   Run simulation, record metrics.

4. **Scenario C: Emergency evacuation** (extreme surge):
   ```yaml
   peak_hours:
     - start: 18
       end: 19
       passengers_per_10min: 500
   ```
   Run simulation, record metrics.

### Analysis Questions

1. **Which scenario creates the largest queues?**
   - Scenario: _______________________________
   - Why: _______________________________

2. **For the concert scenario (longer but lower peak), how many extra trains are deployed compared to the football match?**
   - Football: _____ trains
   - Concert: _____ trains
   - Difference: _______________________________

3. **In the emergency evacuation scenario, does the system cope?**
   - Maximum queue size: _______________________________
   - Can trains handle demand? yes/no
   - What breaks first: _______________________________

4. **How would you adjust the system to handle the evacuation scenario?**
   - Option 1: _______________________________
   - Option 2: _______________________________
   - Option 3: _______________________________

### Expected Observations

- **Sustained high demand** (concert) may stress system more than brief spike (football)
- **Double peaks** create two deployment windows
- **Extreme surges** reveal system breaking points
- **Arrival rate shape** matters as much as total volume

### Extension

Visualize arrival patterns:
```python
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# Create 24-hour profile
hours = list(range(24))
rates = [source.get_arrival_rate(h) for h in hours]

plt.plot(hours, rates, marker='o')
plt.axhline(y=250, color='r', linestyle='--', label='Threshold')
plt.xlabel('Hour of Day')
plt.ylabel('Passengers per 10min')
plt.title('Passenger Arrival Profile')
plt.grid(True)
plt.legend()
plt.show()
```

---

## Exercise 3: Adjust Dispatcher Threshold

**Goal**: Learn how the control center threshold affects system responsiveness and efficiency.

**Background**: The dispatcher triggers extra trains when waiting passengers exceed 250. This threshold controls the trade-off between service quality (shorter waits) and operational cost (fewer extra trains).

### Steps

1. **Conservative approach** (low threshold, more trains):
   - Open `config.yaml`
   - Change `dispatcher.waiting_threshold` to `150`
   - Run `05_train_full_simulation.ipynb`
   - Record: extra trains _____, avg queue _____, max queue _____

2. **Current approach** (baseline):
   - Set threshold to `250`
   - Run simulation
   - Record same metrics

3. **Tolerant approach** (high threshold, fewer trains):
   - Set threshold to `350`
   - Run simulation
   - Record same metrics

4. **Reactive only** (emergency mode):
   - Set threshold to `500`
   - Run simulation
   - Record same metrics

### Analysis Questions

1. **How does threshold affect extra trains deployed?**
   - At 150: _____ trains deployed
   - At 250: _____ trains deployed
   - At 350: _____ trains deployed
   - At 500: _____ trains deployed
   - Relationship: _______________________________

2. **What is the impact on average queue size?**
   | Threshold | Avg Queue | Max Queue | Avg Wait (sec) |
   |-----------|-----------|-----------|----------------|
   | 150       |           |           |                |
   | 250       |           |           |                |
   | 350       |           |           |                |
   | 500       |           |           |                |

3. **Calculate cost-benefit ratio**:
   Assume:
   - Extra train deployment costs 100 credits
   - Each minute of passenger wait time costs 2 credits per passenger
   
   For threshold 150:
   - Train cost: _____ trains × 100 = _____
   - Wait cost: _____ avg queue × _____ avg wait × 2 = _____
   - Total: _____
   
   Repeat for other thresholds. Which is most cost-effective?

4. **What happens if threshold is above peak demand?**
   - Observed behavior: _______________________________
   - Queue growth: _______________________________
   - System stability: _______________________________

### Expected Observations

- **Lower threshold** → More trains, shorter waits, higher cost
- **Higher threshold** → Fewer trains, longer waits, lower cost
- **Optimal threshold** balances operational cost with service quality
- **Too high threshold** → System may not respond to genuine overload

### Extension

Dynamic threshold adjustment:
- Modify `ControlCenterAgent.evaluate_threshold()` to use different thresholds for different hours
- Example: 200 during peak, 300 during off-peak
- Test whether adaptive thresholds improve performance

```python
def evaluate_threshold(self, station_name, waiting_count):
    current_hour = datetime.now().hour
    
    # Use lower threshold during known peak hours
    if 17 <= current_hour <= 20:
        threshold = 200
    else:
        threshold = 300
    
    return waiting_count > threshold
```

---

## Exercise 4: Add Weather Impact

**Goal**: Extend the simulation with environmental factors that affect train operations.

**Background**: Real-world train systems face delays from weather, mechanical issues, or track maintenance. You'll add a weather system that randomly delays trains, simulating storms or snow.

### Part A: Add Weather Data Model

1. **Create weather states**:
   Open `src/simulated_city/agents.py` and add:
   ```python
   from enum import Enum
   
   class WeatherCondition(Enum):
       CLEAR = "clear"
       RAIN = "rain"
       STORM = "storm"
       SNOW = "snow"
   
   @dataclass
   class WeatherState:
       """Current weather conditions affecting train operations."""
       condition: WeatherCondition
       delay_multiplier: float  # 1.0 = normal, 1.5 = 50% slower
       
       def get_travel_time(self, base_time_seconds: float) -> float:
           """Calculate actual travel time with weather delay."""
           return base_time_seconds * self.delay_multiplier
   ```

2. **Add to SimulationState**:
   ```python
   @dataclass
   class SimulationState:
       # ... existing fields ...
       weather: WeatherState = field(
           default_factory=lambda: WeatherState(
               WeatherCondition.CLEAR,
               delay_multiplier=1.0
           )
       )
   ```

### Part B: Create Weather Agent

1. **Implement WeatherAgent**:
   ```python
   class WeatherAgent:
       """Simulates changing weather conditions."""
       
       def __init__(self, mqtt_publisher, mqtt_base_topic):
           self.mqtt_publisher = mqtt_publisher
           self.mqtt_base_topic = mqtt_base_topic
           self._running = False
       
       def generate_weather(self) -> WeatherState:
           """Randomly generate weather with realistic probabilities."""
           import random
           
           conditions = [
               (WeatherCondition.CLEAR, 0.7, 1.0),
               (WeatherCondition.RAIN, 0.2, 1.2),
               (WeatherCondition.STORM, 0.05, 1.5),
               (WeatherCondition.SNOW, 0.05, 1.8),
           ]
           
           rand = random.random()
           cumulative = 0.0
           
           for condition, probability, delay in conditions:
               cumulative += probability
               if rand < cumulative:
                   return WeatherState(condition, delay)
           
           return WeatherState(WeatherCondition.CLEAR, 1.0)
       
       def publish_weather(self, weather: WeatherState):
           """Publish weather update to MQTT."""
           import json
           
           payload = {
               "condition": weather.condition.value,
               "delay_multiplier": weather.delay_multiplier,
               "timestamp": datetime.now().isoformat(),
           }
           
           topic = f"{self.mqtt_base_topic}/weather/current"
           self.mqtt_publisher.publish_json(topic, json.dumps(payload), qos=0)
       
       async def run(self, simulation_state, interval_seconds=300):
           """Main weather loop - change weather every 5 minutes."""
           import asyncio
           
           self._running = True
           
           while self._running:
               # Generate new weather
               weather = self.generate_weather()
               simulation_state.weather = weather
               
               # Publish update
               self.publish_weather(weather)
               
               print(f"Weather: {weather.condition.value} (delay: {weather.delay_multiplier}x)")
               
               await asyncio.sleep(interval_seconds)
       
       def stop(self):
           self._running = False
   ```

### Part C: Modify TrainAgent to Use Weather

1. **Update TrainAgent.run() method**:
   Find this line in `TrainAgent.run()`:
   ```python
   await asyncio.sleep(travel_time_seconds)
   ```
   
   Replace with:
   ```python
   # Apply weather delay
   actual_travel_time = simulation_state.weather.get_travel_time(travel_time_seconds)
   if actual_travel_time > travel_time_seconds:
       print(f"  {self.train.id}: Weather delay! {travel_time_seconds}s → {actual_travel_time:.1f}s")
   await asyncio.sleep(actual_travel_time)
   ```

### Part D: Test Weather Impact

1. **Add weather to configuration**:
   In `config.yaml`, add:
   ```yaml
   train_network:
     # ... existing config ...
     weather:
       enabled: true
       change_interval_seconds: 300  # Change every 5 minutes
   ```

2. **Run simulation with weather**:
   - Open `05_train_full_simulation.ipynb`
   - Add weather agent to the simulation:
     ```python
     weather_agent = WeatherAgent(publisher, config.train_network.mqtt_base_topic)
     
     # Add to asyncio tasks
     tasks = [
         # ... existing tasks ...
         weather_agent.run(sim_state, interval_seconds=300),
     ]
     ```
   - Run for 30 minutes
   - Observe train delays during storms

### Analysis Questions

1. **How does weather affect throughput?**
   - Clear weather: _____ passengers boarded in 30 min
   - With storms: _____ passengers boarded in 30 min
   - Reduction: _____% 

2. **Do weather delays trigger more extra train deployments?**
   - Without weather: _____ extra trains
   - With weather: _____ extra trains
   - Why: _______________________________

3. **What is the cumulative delay impact?**
   - Track total delay hours: `(actual_time - base_time) × num_trips`
   - Result: _______________________________

4. **How would you mitigate weather impact?**
   - Strategy 1: _______________________________
   - Strategy 2: _______________________________
   - Strategy 3: _______________________________

### Expected Observations

- **Storms** (1.5x delay) significantly reduce train frequency
- **Queue sizes grow** during bad weather
- **Extra trains help** but may also be delayed
- **System capacity** decreases proportionally to delay multiplier

### Extension Ideas

1. **Weather forecasting**:
   - Control center receives weather forecasts
   - Pre-deploys extra trains before storms
   - Compare reactive vs proactive strategies

2. **Station-specific weather**:
   - Different weather at different stations
   - Delays only affect certain route segments
   - More realistic modeling

3. **Weather severity levels**:
   - Add "traffic control" mode during severe weather
   - Reduce train speeds (higher delay multiplier)
   - Or suspend service entirely (simulation freezes)

4. **Historical weather patterns**:
   - Load real weather data from CSV
   - Replay historical storm events
   - Validate system resilience against known conditions

---

## Challenge Exercises

### Challenge 1: Predictive Dispatch

**Goal**: Deploy extra trains *before* queues exceed threshold.

Modify `ControlCenterAgent` to:
- Track queue growth rate (passengers arriving per minute)
- Predict queue size 10 minutes in the future
- Dispatch proactively if predicted size exceeds threshold

Compare proactive vs reactive performance.

### Challenge 2: Station Priority

**Goal**: Prioritize extra trains to stations with worst conditions.

When multiple stations exceed threshold:
- Calculate "urgency score" = (waiting_count / threshold) × avg_wait_time
- Deploy to highest urgency first
- Test with asymmetric loads across stations

### Challenge 3: Dynamic Routing

**Goal**: Allow trains to skip stations with no waiting passengers.

Modify `TrainAgent` to:
- Check queue size before arriving at station
- Skip station if queue is empty (save travel time)
- Publish routing decisions to MQTT

Measure throughput improvement.

### Challenge 4: Multi-Route Network

**Goal**: Expand from single route to network with transfers.

Add:
- Multiple parallel routes
- Transfer stations connecting routes
- Passenger agents that choose routes
- Route selection logic based on wait times

Simulate a realistic city network.

---

## Reflection Questions

After completing these exercises, reflect on:

1. **What are the most important factors affecting train network performance?**
   - Top 3 factors: _______________________________

2. **How does agent-based modeling help understand complex systems?**
   - Key insight: _______________________________

3. **What real-world scenarios would benefit from this type of simulation?**
   - Example 1: _______________________________
   - Example 2: _______________________________
   - Example 3: _______________________________

4. **How could this simulation be extended for other domains?**
   - Domain: _______________________________
   - Agents needed: _______________________________
   - Key metrics: _______________________________

5. **What did you learn about distributed systems and MQTT?**
   - Learning: _______________________________

---

## Additional Resources

- **Documentation**: [docs/train_simulation.md](train_simulation.md)
- **MQTT Guide**: [docs/mqtt.md](mqtt.md)
- **Configuration**: [docs/config.md](config.md)
- **Setup Instructions**: [docs/setup.md](setup.md)

## Getting Help

If you encounter issues:
1. Check error messages carefully
2. Verify MQTT broker is running: `lsof -i :1883`
3. Restart Jupyter kernel: Kernel → Restart
4. Review test files for working examples: `tests/test_*.py`
5. Ask for help with specific error messages

---

**Happy simulating!** 🚂
