# Advanced Weather-Aware Multi-Agent Demo

## Concept Overview

This demo extends the basic person walker visualization with a **weather system** that affects agent behavior in real-time. It demonstrates:

1. **Multi-agent coordination over MQTT** — independent person agents react to shared environmental events (weather)
2. **Spatial reasoning** — agents calculate distances to shelters (cafes) and navigate autonomously
3. **State machines** — agents switch between "walking" and "sheltering" modes based on weather
4. **Pub/Sub patterns** — agents act as both publishers (location) and subscribers (weather, cafe locations)
5. **Live visualization** — the map reflects both agent movement and environmental changes (sky color, basemap)

### The Story

On a sunny day, several people walk randomly around Copenhagen City Hall. When rain arrives (published by a weather controller), each person immediately finds the nearest coffee shop and runs there for shelter. Once the rain clears, they resume their random walk. The map visualizer watches everyone and updates the atmosphere (dark sky, dark theme) when it rains.

**Key learning goals:**
- MQTT message routing and filtering (`+` wildcard subscriptions)
- Haversine distance calculations for spatial queries
- Waypoint generation for smooth navigation
- Async event handling (MQTT callbacks driving behavior changes)
- Decoupled system design (agents don't know about each other, only about weather)

---

## System Architecture

```
┌─────────────────────┐
│ Weather Controller  │ ──→ MQTT: weather/status
│  (30s cycle)        │     {"state": "sunny"|"rain", ...}
└─────────────────────┘

                           MQTT Broker

┌─────────────────────┐    ┌────────────────────┐
│  Person Walkers     │    │  Map Viewer         │
│  (Multiple)         │    │                    │
│                     │    │ • Shows 5 cafes    │
│ • Subscribe to      │    │ • Updates markers  │
│   weather/status    │    │ • Changes basemap  │
│ • Subscribe to      │    │   on rain          │
│   cafes/locations   │    │ • Publishes cafe   │
│ • Publish location  │    │   locations        │
│   once/sec          │    │ • Visual feedback  │
│ • Navigate to cafe  │    │                    │
│   on rain           ├───→ MQTT: persons/+/location
│ • Resume walk on    │     MQTT: weather/status
│   sunny             │     MQTT: cafes/locations
└─────────────────────┘    └────────────────────┘
```

---

## MQTT Topic Reference

### 1. **weather/status** — Central weather broadcasts

| Field | Type | Example | Description |
|-------|------|---------|-------------|
| `state` | string | `"sunny"` or `"rain"` | Current weather condition |
| `timestamp` | float | `1708593600.123` | Unix timestamp of state change |
| `cycle` | int | `3` | Which cycle number (for logging) |

**Publisher:** `weather_controller.ipynb`  
**Subscribers:** `map_viewer_advanced.ipynb`, all `person_walker_advanced.ipynb` instances  
**Frequency:** Every 20 or 10 seconds (depending on phase)  
**QoS:** 0 (fire-and-forget)

**Example message:**
```json
{
  "state": "rain",
  "timestamp": 1708593620.456,
  "cycle": 1
}
```

---

### 2. **persons/{name}/location** — Per-agent location updates

| Field | Type | Example | Description |
|-------|------|---------|-------------|
| `lng` | float | `12.5715` | Longitude (WGS84) |
| `lat` | float | `55.6765` | Latitude (WGS84) |
| `color` | string | `"#e74c3c"` | Hex color for marker |
| `name` | string | `"Alice"` | Person identifier |
| `timestamp` | float | `1708593600.789` | Unix timestamp |

**Publisher:** Each `person_walker_advanced.ipynb` instance  
**Subscribers:** `map_viewer_advanced.ipynb` (uses wildcard `persons/+/location`)  
**Frequency:** Once per second (after each step)  
**QoS:** 0 (fire-and-forget)

**Example message:**
```json
{
  "lng": 12.5715,
  "lat": 55.6765,
  "color": "#e74c3c",
  "name": "Alice",
  "timestamp": 1708593620.789
}
```

---

### 3. **cafes/locations** — Discoverable shelter locations

| Field | Type | Example | Description |
|-------|------|---------|-------------|
| `cafes` | array | See below | List of all cafe locations and metadata |
| `cafes[*].id` | string | `"cafe-1"` | Stable cafe identifier |
| `cafes[*].name` | string | `"Café Nordic"` | Human-readable name |
| `cafes[*].lng` | float | `12.5699` | Longitude (WGS84) |
| `cafes[*].lat` | float | `55.6763` | Latitude (WGS84) |
| `timestamp` | float | `1708593600.999` | Unix timestamp of publication |

**Publisher:** `map_viewer_advanced.ipynb` (broadcasts every 5 seconds)  
**Subscribers:** All `person_walker_advanced.ipynb` instances  
**Frequency:** Every 5 seconds  
**QoS:** 0 (fire-and-forget)

**Example message:**
```json
{
  "cafes": [
    {
      "id": "cafe-1",
      "name": "Café Nordic",
      "lng": 12.5699,
      "lat": 55.6763
    },
    {
      "id": "cafe-2",
      "name": "Kaffebar Central",
      "lng": 12.5669,
      "lat": 55.6758
    }
  ],
  "timestamp": 1708593620.999
}
```

---

## Implementation Plan

### Phase 1: Weather Control

**File:** `weather_controller.ipynb`

1. Connect to MQTT broker
2. Enter main loop:
   - Publish `{"state": "sunny", ...}` to `weather/status`
   - Sleep 20 seconds
   - Publish `{"state": "rain", ...}` to `weather/status`
   - Sleep 10 seconds
   - Repeat

**Key code pattern:**
```python
async def weather_controller():
    while True:
        publisher.publish_json("weather/status", json.dumps({"state": "sunny", ...}))
        await asyncio.sleep(20)
        publisher.publish_json("weather/status", json.dumps({"state": "rain", ...}))
        await asyncio.sleep(10)
```

---

### Phase 2: Map Visualization & Cafe Broadcasting

**File:** `map_viewer_advanced.ipynb`

1. Create `LiveMapLibreMap` centered on City Hall (Copenhagen)
2. Add initial basemap: `OpenStreetMap.Mapnik` (light)
3. Set sunny sky: `m.set_sky(sky_color="#88C6FC", ...)`
4. Add 5 static coffee shop markers with black color (`#1a1a1a`)
5. Connect to MQTT as both publisher and subscriber
6. Subscribe to:
   - `persons/+/location` (all person updates)
   - `weather/status` (weather changes)
7. On `persons/{name}/location`:
   - Extract `lng`, `lat`, `color`, `name`
   - Call `m.move_marker(f"person-{name}", (lng, lat), color=color)`
8. On `weather/status`:
   - If state is `"rain"`:
     - Set dark sky: `m.set_sky(sky_color="#010101", ...)`
     - Hide light basemap: `m.set_visibility("OpenStreetMap.Mapnik", False)`
     - Add dark basemap: `m.add_basemap("CartoDB.DarkMatter")`
   - If state is `"sunny"`:
     - Reset sky to light: `m.set_sky(sky_color="#88C6FC", ...)`
     - Hide dark basemap: `m.set_visibility("CartoDB.DarkMatter", False)`
     - Restore light basemap: `m.add_basemap("OpenStreetMap.Mapnik")`
9. Broadcast cafe locations every 5 seconds on `cafes/locations` (so walkers can discover them without hardcoding)

**Key code pattern:**
```python
def on_message_dispatch(client, userdata, message):
    if message.topic.startswith("persons/"):
        data = json.loads(message.payload.decode())
        m.move_marker(f"person-{data['name']}", (data['lng'], data['lat']), color=data['color'])
    elif message.topic == "weather/status":
        state = json.loads(message.payload.decode())["state"]
        if state == "rain":
            m.set_sky(sky_color="#010101", ...)
            m.add_basemap("CartoDB.DarkMatter")

connector.client.on_message = on_message_dispatch
connector.client.subscribe("persons/+/location")
connector.client.subscribe("weather/status")
```

---

### Phase 3: Weather-Aware Person Walkers

**File:** `person_walker_advanced.ipynb`

1. **Initialization:**
   - Accept user inputs: `PERSON_NAME`, `COLOR`
   - Connect to MQTT as both publisher and subscriber
   - Define helper functions: `haversine_m()`, `find_nearest_cafe()`, `generate_waypoints()`
   - Initialize state dict: `{"weather": "sunny", "cafes": [], "is_seeking_shelter": False, "target_cafe": None, "waypoints": [], ...}`

2. **Subscribe to:**
   - `weather/status` → update `state["weather"]`
   - `cafes/locations` → update `state["cafes"]` list

3. **Main walk loop (once per second):**
   
   **a) Check weather transition:**
   - If weather changed from sunny → rain:
     - Set `state["is_seeking_shelter"] = True`
     - Get current position: `(lng, lat)`
     - Find nearest cafe: `find_nearest_cafe(current_pos, state["cafes"])`
     - Generate waypoints: `generate_waypoints(current_pos, cafe_pos, num_waypoints=...)`
   - If weather changed from rain → sunny:
     - Set `state["is_seeking_shelter"] = False`
     - Clear waypoints and target cafe
   
   **b) Calculate next position:**
   - If `is_seeking_shelter` and waypoints exist:
     - Move to next waypoint: `next_pos = state["waypoints"][waypoint_index]`
     - Convert to x_m, y_m
     - Increment waypoint index
   - Else (normal walk):
     - Generate random direction: `theta = random() * 2π`
     - Update position: `x_m += step_m * cos(theta); y_m += step_m * sin(theta)`
     - Enforce soft boundary (max radius)
   
   **c) Publish location:**
   - Convert x_m, y_m back to lng/lat
   - Create message: `{"lng": ..., "lat": ..., "color": ..., "name": ..., "timestamp": ...}`
   - Publish to `persons/{PERSON_NAME}/location`

4. **Async concurrency:**
   - MQTT callbacks (`on_weather_message`, `on_cafes_message`) update `state` dict
   - Main walk loop reads from `state` dict and reacts
   - No blocking calls in callbacks (follow MQTT threading rule)

**Key code pattern:**
```python
async def advanced_random_walk_publisher(...):
    while True:
        current_weather = state["weather"]
        
        if current_weather == "rain" and not state["is_seeking_shelter"]:
            state["is_seeking_shelter"] = True
            cafe = find_nearest_cafe(current_pos, state["cafes"])
            state["waypoints"] = generate_waypoints(current_pos, cafe_pos, num_waypoints=10)
        
        elif state["is_seeking_shelter"]:
            if state["waypoint_index"] < len(state["waypoints"]):
                next_pos = state["waypoints"][state["waypoint_index"]]
                x_m, y_m = convert_to_meters(next_pos)
                state["waypoint_index"] += 1
        else:
            # Normal random walk
            theta = random() * 2 * math.pi
            x_m += step_m * cos(theta)
            y_m += step_m * sin(theta)
        
        lng, lat = convert_to_lnglat(x_m, y_m)
        publisher.publish_json(f"persons/{PERSON_NAME}/location", 
                               json.dumps({"lng": lng, "lat": lat, "color": COLOR, ...}))
        
        await asyncio.sleep(1.0)
```

---

## Execution Flow (Timeline)

```
Time  | Weather Controller    | Map Viewer                  | Person Walkers (Alice, Bob)
------|----------------------|-----------------------------|--------------------------
 0s   | START                | START, show cafes           | START, gen. random walk
      | → sunny              | show light sky/basemap      | walking randomly
      |                      | publish cafes/locations     | subscribe weather, cafes
      |                      | subscribe weather, persons  |
      |                      |                             | publish location (1/sec)
      |                      |                             |
 5s   | (sunny)              | receive location updates    | running walk
      |                      | move markers on map         |
      |                      | republish cafe locations    |
      |                      |                             |
10s   | (sunny)              | (sunny)                     | (sunny, walking)
      |                      |                             |
20s   |                      |                             |
      | → rain               | receive weather/status      | receive weather/status
      | publish rain msg     | → set dark sky              | → seek nearest cafe
      |                      | → switch to DarkMatter      | → calc waypoints
      |                      | visual: sky turns dark      | → start navigating
      |                      |                             |
25s   | (rain: 5s elapsed)   | (rain)                      | running to cafe
      |                      | markers still visible       | moving along waypoints
      |                      | dark background             | publish location
      |                      |                             |
30s   | → sunny              | receive weather/status      | receive weather/status
      | publish sunny msg    | → set light sky             | → stop sheltering
      |                      | → switch to OSM.Mapnik      | → resume random walk
      |                      | visual: sky turns light     | → clear waypoints
      |                      |                             |
...   | (repeats every 30s)  | (repeats every 30s)         | (repeats every 30s)
```

---

## Concepts Demonstrated

| Concept | Implementation | Learning Value |
|---------|---|---|
| **MQTT Pub/Sub** | Weather → all agents; Agents → location (1-to-many, many-to-1) | Decoupling via messaging |
| **Wildcards** | `persons/+/location` matches all agents | Scalability without hardcoding |
| **State machines** | Sunny ↔ Sheltering modes | Event-driven behavior |
| **Haversine distance** | Find nearest cafe to current position | Geospatial computation |
| **Waypoint navigation** | Linear interpolation between start and cafe | Smooth movement |
| **Async concurrency** | MQTT callbacks + main loop | Non-blocking I/O |
| **Visual feedback** | Map sky/basemap change on weather | Real-time environment rendering |
| **Decoupled agents** | Walkers don't know about each other | Scalable multi-agent systems |

---

## Files Overview

| File | Role | Inputs | Outputs |
|------|------|--------|---------|
| `weather_controller.ipynb` | Environment driver | None | `weather/status` every 20/10s |
| `map_viewer_advanced.ipynb` | Visualization & cafe broadcaster | `persons/+/location`, `weather/status` | Map display, `cafes/locations` every 5s |
| `person_walker_advanced.ipynb` | Individual agent | `weather/status`, `cafes/locations` | `persons/{name}/location` every 1s |

---

## Running the Demo

### Setup (one-time)

1. Ensure MQTT broker is running (e.g., `mosquitto`)
2. All notebooks use `.env` for credentials (see `config.yaml`)

### Execution Order

1. **Start map viewer first:**
   ```
   Open notebooks/map_viewer_advanced.ipynb
   Navigate to the last cell (stop button)
   Choose "Run → Run All Above"
   ```
   ✓ You'll see City Hall, 5 black cafe markers, light sky
   ⚠️ **Important:** Do NOT run the last cell (it stops the simulation)

2. **Start weather controller (second):**
   ```
   Open notebooks/weather_controller.ipynb
   Navigate to the last cell (stop button)
   Choose "Run → Run All Above"
   ```
   ✓ Watch console: ☀️ SUNNY (20s) → 🌧️ RAIN (10s) → repeat  
   ✓ Watch map: sky and basemap toggle
   ⚠️ **Important:** Do NOT run the last cell (it stops the simulation)

3. **Start person walkers (third, multiple instances):**
   ```
   # Instance 1 (Alice)
   Open notebooks/person_walker_advanced.ipynb
   Edit Cell 2: PERSON_NAME = "Alice", COLOR = "#e74c3c"
   Navigate to the last cell (stop button)
   Choose "Run → Run All Above"
   
   # Instance 2 (Bob, in separate window/tab)
   Open notebooks/person_walker_advanced.ipynb again
   Edit Cell 2: PERSON_NAME = "Bob", COLOR = "#3498db"
   Navigate to the last cell (stop button)
   Choose "Run → Run All Above"
   
   # Instance 3 (Charlie)
   Edit Cell 2: PERSON_NAME = "Charlie", COLOR = "#2ecc71"
   Navigate to the last cell (stop button)
   Choose "Run → Run All Above"
   ```
   ⚠️ **Important:** Do NOT run the last cell in any notebook (it stops that agent's simulation)

### What to Watch

- **Sunny phase (20s):** All persons walk randomly around City Hall
- **Rain transition:** Watch all persons **immediately** converge on nearest cafe
  - Each person takes their own shortest path
  - Smooth waypoint navigation (no teleporting)
- **Sunny transition:** All persons leave cafes and resume walking
- **Map appearance:**
  - Light theme when sunny (light sky, OSM Mapnik)
  - Dark theme when raining (dark sky, CartoDB DarkMatter)

---

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| Persons all same color | Map is using default color | Ensure `person_walker_advanced.ipynb` publishes color in message |
| No weather changes visible | `map_viewer_advanced.ipynb` not subscribed | Check `connector.client.subscribe("weather/status", qos=0)` |
| Persons don't move to cafes | No cafe data received | Check `cafes/locations` is being published; wait 5s for initial broadcast |
| Dark basemap doesn't appear | Layer management issue | May need to refresh notebook; check anymap-ts documentation |
| MQTT not connecting | Broker not running | Start MQTT: `brew services start mosquitto` (macOS) or `docker run -p 1883:1883 eclipse-mosquitto` |

---

## Extensions & Ideas

- **Wind direction:** Add wind vector to weather messages; agents adjust path differently
- **Crowds:** Add congestion logic; crowded cafes become less attractive
- **Attractions:** Extend to multi-location discovery (shops, parks) with different behaviors
- **Performance:** Add trip logging to MQTT; replay and analyze agent paths
- **UI controls:** Add map UI buttons to trigger manual weather changes
- **Multi-weather:** Extend from binary (sunny/rain) to multi-state (snow, fog, etc.)

