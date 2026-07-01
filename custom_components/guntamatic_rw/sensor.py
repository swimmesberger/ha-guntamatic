"""Sensor platform: one entity per (non-boolean) DAQ channel."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import GuntamaticConfigEntry, GuntamaticDataUpdateCoordinator
from .entity import GuntamaticEntity

# Read-only platform: allow unlimited parallel updates.
PARALLEL_UPDATES = 0

# Maps the device unit string -> (native unit, device_class, state_class).
_UNIT_MAP: dict[str, tuple[str, SensorDeviceClass | None, SensorStateClass]] = {
    "°C": (UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    "%": (PERCENTAGE, None, SensorStateClass.MEASUREMENT),
    # Duration channels can count up (operating time) or DOWN (service/ash
    # countdown), so MEASUREMENT is the only safe state class.
    "h": (UnitOfTime.HOURS, SensorDeviceClass.DURATION, SensorStateClass.MEASUREMENT),
    "d": (UnitOfTime.DAYS, SensorDeviceClass.DURATION, SensorStateClass.MEASUREMENT),
    # Fuel counter is a genuine cumulative total.
    "m3": (UnitOfVolume.CUBIC_METERS, SensorDeviceClass.VOLUME, SensorStateClass.TOTAL_INCREASING),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GuntamaticConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors from the cached channel descriptions."""
    coordinator = entry.runtime_data
    entities = [
        GuntamaticSensor(coordinator, channel_id)
        for channel_id, channel in coordinator.data.items()
        # boolean channels are exposed as binary sensors instead
        if channel.description.type != "bool"
    ]
    async_add_entities(entities)


class GuntamaticSensor(GuntamaticEntity, SensorEntity):
    """A sensor backed by one DAQ channel."""

    def __init__(
        self, coordinator: GuntamaticDataUpdateCoordinator, channel_id: int
    ) -> None:
        """Initialize the sensor for a given channel id."""
        super().__init__(coordinator)
        self._channel_id = channel_id
        desc = coordinator.data[channel_id].description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{channel_id}"
        self._attr_name = desc.name

        if desc.type in ("float", "int"):
            if desc.unit and desc.unit in _UNIT_MAP:
                unit, device_class, state_class = _UNIT_MAP[desc.unit]
                self._attr_native_unit_of_measurement = unit
                self._attr_device_class = device_class
                self._attr_state_class = state_class
            else:
                # Numeric channel without a (known) unit.
                self._attr_state_class = SensorStateClass.MEASUREMENT
        else:
            # Free-form text / enum-like status channel (or any non-numeric type).
            # Never declare a numeric state_class: HA would reject the string value
            # with a ValueError on every update.
            self._attr_native_unit_of_measurement = None
            self._attr_device_class = None
            self._attr_state_class = None

    @property
    def available(self) -> bool:
        """Return True if the channel is present in the latest update."""
        return super().available and self._channel_id in self.coordinator.data

    @property
    def native_value(self) -> float | int | str | None:
        """Return the channel's current value."""
        channel = self.coordinator.data.get(self._channel_id)
        if channel is None:
            return None
        value = channel.value
        if value is None:
            return None
        if channel.description.type in ("float", "int"):
            try:
                return float(value) if channel.description.type == "float" else int(value)
            except (TypeError, ValueError):
                return None
        return str(value)
