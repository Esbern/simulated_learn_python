from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
import yaml


@dataclass(frozen=True, slots=True)
class MqttConfig:
    host: str
    port: int
    tls: bool
    username: str | None
    password: str | None = field(repr=False)
    client_id_prefix: str
    keepalive_s: int


@dataclass(frozen=True, slots=True)
class StationLocation:
    """Geographic location of a station."""
    lat: float
    lon: float


@dataclass(frozen=True, slots=True)
class StationConfig:
    """Configuration for a single station in the train network."""
    name: str
    type: str  # "entry" or "exit"
    location: StationLocation
    exit_percentage: int | None = None  # Only for exit stations


@dataclass(frozen=True, slots=True)
class TrainConfig:
    """Train specifications."""
    capacity: int
    departure_interval_minutes: int
    base_occupancy_percent: int


@dataclass(frozen=True, slots=True)
class PeakHourConfig:
    """Passenger arrival configuration for peak hours."""
    start: int  # Hour (0-23)
    end: int  # Hour (0-23)
    passengers_per_10min: int


@dataclass(frozen=True, slots=True)
class PassengerFlowConfig:
    """Passenger arrival rates by time of day."""
    peak_hours: list[PeakHourConfig]
    off_peak_passengers_per_10min: int


@dataclass(frozen=True, slots=True)
class DispatcherConfig:
    """Control center dispatcher rules."""
    waiting_threshold: int  # Deploy extra train if waiting > this


@dataclass(frozen=True, slots=True)
class TrainNetworkConfig:
    """Train network simulation configuration."""
    mqtt_base_topic: str
    train: TrainConfig
    route: list[StationConfig]
    passenger_flow: PassengerFlowConfig
    dispatcher: DispatcherConfig


@dataclass(frozen=True, slots=True)
class AppConfig:
    mqtt: MqttConfig
    train_network: TrainNetworkConfig | None = None


def load_config(path: str | Path = "config.yaml") -> AppConfig:
    # Load a local .env if present (it is gitignored by default).
    # This makes workshop setup easier while keeping secrets out of git.
    load_dotenv(override=False)

    resolved_path = _resolve_default_config_path(path)
    data = _load_yaml_dict(resolved_path)
    mqtt = data.get("mqtt") or {}

    host = str(mqtt.get("host") or "localhost")
    port = int(mqtt.get("port") or 1883)
    tls = bool(mqtt.get("tls") or False)

    username_env = mqtt.get("username_env")
    password_env = mqtt.get("password_env")
    username = os.getenv(str(username_env)) if username_env else None
    password = os.getenv(str(password_env)) if password_env else None

    client_id_prefix = str(mqtt.get("client_id_prefix") or "simcity")
    keepalive_s = int(mqtt.get("keepalive_s") or 60)

    mqtt_config = MqttConfig(
        host=host,
        port=port,
        tls=tls,
        username=username,
        password=password,
        client_id_prefix=client_id_prefix,
        keepalive_s=keepalive_s,
    )

    # Load train network configuration if present
    train_network_config = None
    train_network_data = data.get("train_network")
    if train_network_data:
        train_network_config = _load_train_network_config(train_network_data)

    return AppConfig(
        mqtt=mqtt_config,
        train_network=train_network_config,
    )


def _load_train_network_config(data: dict[str, Any]) -> TrainNetworkConfig:
    """Parse train network configuration from YAML data."""
    mqtt_base_topic = str(data.get("mqtt_base_topic") or "train_network")

    # Load train config
    train_data = data.get("train") or {}
    train_config = TrainConfig(
        capacity=int(train_data.get("capacity") or 300),
        departure_interval_minutes=int(train_data.get("departure_interval_minutes") or 5),
        base_occupancy_percent=int(train_data.get("base_occupancy_percent") or 16),
    )

    # Load route stations
    route_data = data.get("route") or []
    route = []
    for station_data in route_data:
        location_data = station_data.get("location") or {}
        location = StationLocation(
            lat=float(location_data.get("lat") or 0.0),
            lon=float(location_data.get("lon") or 0.0),
        )
        station = StationConfig(
            name=str(station_data.get("name") or ""),
            type=str(station_data.get("type") or "entry"),
            location=location,
            exit_percentage=station_data.get("exit_percentage"),
        )
        route.append(station)

    # Load passenger flow config
    flow_data = data.get("passenger_flow") or {}
    peak_hours_data = flow_data.get("peak_hours") or []
    peak_hours = [
        PeakHourConfig(
            start=int(ph.get("start") or 0),
            end=int(ph.get("end") or 0),
            passengers_per_10min=int(ph.get("passengers_per_10min") or 0),
        )
        for ph in peak_hours_data
    ]
    passenger_flow = PassengerFlowConfig(
        peak_hours=peak_hours,
        off_peak_passengers_per_10min=int(flow_data.get("off_peak_passengers_per_10min") or 50),
    )

    # Load dispatcher config
    dispatcher_data = data.get("dispatcher") or {}
    dispatcher = DispatcherConfig(
        waiting_threshold=int(dispatcher_data.get("waiting_threshold") or 250),
    )

    return TrainNetworkConfig(
        mqtt_base_topic=mqtt_base_topic,
        train=train_config,
        route=route,
        passenger_flow=passenger_flow,
        dispatcher=dispatcher,
    )


def _load_yaml_dict(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}

    content = p.read_text(encoding="utf-8")
    loaded = yaml.safe_load(content)
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Config file {p} must contain a YAML mapping at top level")
    return loaded


def _resolve_default_config_path(path: str | Path) -> Path:
    """Resolve a config path in a notebook-friendly way.

    When `load_config()` is called with the default relative filename
    (`config.yaml`), users often run code from a subdirectory (e.g. `notebooks/`).
    In that case we search parent directories so `config.yaml` at repo root is
    still discovered.

    If a custom path is provided (including nested relative paths), we do not
    change it.
    """

    p = Path(path)

    # Absolute paths, or already-existing relative paths, are used as-is.
    if p.is_absolute() or p.exists():
        return p

    # Only apply parent-search for bare filenames like "config.yaml".
    if p.parent != Path("."):
        return p

    def search_upwards(start: Path) -> Path | None:
        for parent in [start, *start.parents]:
            candidate = parent / p.name
            if candidate.exists():
                return candidate
        return None

    found = search_upwards(Path.cwd())
    if found is not None:
        return found

    # If cwd isn't inside the project (common in some notebook setups), also
    # search relative to this installed package location.
    found = search_upwards(Path(__file__).resolve().parent)
    if found is not None:
        return found

    return p
