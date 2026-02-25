"""simulated_city

This package intentionally keeps only workshop-agnostic helpers:
- YAML/.env configuration loading (see :mod:`simulated_city.config`)
- MQTT connection helpers (see :mod:`simulated_city.mqtt`)
- Data models for train network simulation (see :mod:`simulated_city.agents`)

Simulation logic is meant to be implemented by students during the workshop.
"""

from .config import (
	AppConfig,
	DispatcherConfig,
	MqttConfig,
	PassengerFlowConfig,
	PeakHourConfig,
	StationConfig,
	StationLocation,
	TrainConfig,
	TrainNetworkConfig,
	load_config,
)
from .geo import (
	EPSG_25832,
	EPSG_3857,
	epsg25832_to_webmercator,
	transform_many,
	transform_xy,
	webmercator_to_epsg25832,
	wgs2utm,
	utm2wgs,
)
from .mqtt import MqttConnector, MqttPublisher
from .agents import (
	ControlCenterAgent,
	DispatcherAgent,
	Passenger,
	PassengerSourceAgent,
	SensorAgent,
	SimulationState,
	Station,
	StationQueue,
	Train,
	TrainAgent,
	TrainStatus,
)

__all__ = [
	"AppConfig",
	"DispatcherConfig",
	"MqttConfig",
	"PassengerFlowConfig",
	"PeakHourConfig",
	"StationConfig",
	"StationLocation",
	"TrainConfig",
	"TrainNetworkConfig",
	"load_config",
	"EPSG_25832",
	"EPSG_3857",
	"transform_xy",
	"transform_many",
	"webmercator_to_epsg25832",
	"epsg25832_to_webmercator",
	"wgs2utm",
	"utm2wgs",
	"MqttConnector",
	"MqttPublisher",
	"ControlCenterAgent",
	"DispatcherAgent",
	"Passenger",
	"PassengerSourceAgent",
	"SensorAgent",
	"SimulationState",
	"Station",
	"StationQueue",
	"Train",
	"TrainAgent",
	"TrainStatus",
]
