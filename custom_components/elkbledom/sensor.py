from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BLEDOMCoordinator
from .device import BLEDOMInstance

LOG = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][config_entry.entry_id]
    instance = data["instance"]
    coordinator = data["coordinator"]
    async_add_entities([
        BLEDOMRSSISensor(coordinator, instance, config_entry.entry_id),
        BLEDOMTimerOnSensor(coordinator, instance, config_entry.entry_id),
        BLEDOMTimerOffSensor(coordinator, instance, config_entry.entry_id),
        BLEDOMFirmwareVersionSensor(coordinator, instance, config_entry.entry_id),
        BLEDOMConnectionStateSensor(coordinator, instance, config_entry.entry_id),
    ])


class BLEDOMRSSISensor(CoordinatorEntity[BLEDOMCoordinator], SensorEntity):
    """RSSI sensor entity."""

    _attr_has_entity_name = True
    _attr_translation_key = "rssi"
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: BLEDOMCoordinator, bledomInstance: BLEDOMInstance, entry_id: str) -> None:
        super().__init__(coordinator)
        self._instance = bledomInstance
        self._attr_unique_id = f"{self._instance.address}_rssi"
        self._entry_id = entry_id

    @property
    def available(self) -> bool:
        return self._instance.rssi is not None

    @property
    def native_value(self) -> int | None:
        return self._instance.rssi

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={
                (DOMAIN, self._instance.address)
            },
            manufacturer="ELK",
            model=self._instance._model or "BLEDOM",
            connections={(device_registry.CONNECTION_BLUETOOTH, self._instance.address)},
        )


class BLEDOMTimerOnSensor(CoordinatorEntity[BLEDOMCoordinator], SensorEntity):
    """Timer On schedule sensor entity."""

    _attr_has_entity_name = True
    _attr_translation_key = "timer_on"
    _attr_icon = "mdi:timer-play"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: BLEDOMCoordinator, bledomInstance: BLEDOMInstance, entry_id: str) -> None:
        super().__init__(coordinator)
        self._instance = bledomInstance
        self._attr_unique_id = f"{self._instance.address}_timer_on"
        self._entry_id = entry_id

    @property
    def available(self) -> bool:
        return self._instance.timer_on_state is not None

    @property
    def native_value(self) -> str | None:
        state = self._instance.timer_on_state
        if state is None:
            return None
        hour = state.get("hour", 0)
        minute = state.get("minute", 0)
        enabled = state.get("enabled", False)
        return f"{hour:02d}:{minute:02d}" if enabled else "Off"

    @property
    def extra_state_attributes(self) -> dict | None:
        state = self._instance.timer_on_state
        if state is None:
            return None
        days_mask = state.get("days", 0)
        days = []
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for i, name in enumerate(day_names):
            if days_mask & (1 << i):
                days.append(name)
        return {
            "hour": state.get("hour"),
            "minute": state.get("minute"),
            "enabled": state.get("enabled"),
            "days_mask": days_mask,
            "days": ", ".join(days) if days else "None",
        }

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._instance.address)},
            manufacturer="ELK",
            model=self._instance._model or "BLEDOM",
            connections={(device_registry.CONNECTION_BLUETOOTH, self._instance.address)},
        )


class BLEDOMTimerOffSensor(CoordinatorEntity[BLEDOMCoordinator], SensorEntity):
    """Timer Off schedule sensor entity."""

    _attr_has_entity_name = True
    _attr_translation_key = "timer_off"
    _attr_icon = "mdi:timer-stop"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: BLEDOMCoordinator, bledomInstance: BLEDOMInstance, entry_id: str) -> None:
        super().__init__(coordinator)
        self._instance = bledomInstance
        self._attr_unique_id = f"{self._instance.address}_timer_off"
        self._entry_id = entry_id

    @property
    def available(self) -> bool:
        return self._instance.timer_off_state is not None

    @property
    def native_value(self) -> str | None:
        state = self._instance.timer_off_state
        if state is None:
            return None
        hour = state.get("hour", 0)
        minute = state.get("minute", 0)
        enabled = state.get("enabled", False)
        return f"{hour:02d}:{minute:02d}" if enabled else "Off"

    @property
    def extra_state_attributes(self) -> dict | None:
        state = self._instance.timer_off_state
        if state is None:
            return None
        days_mask = state.get("days", 0)
        days = []
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for i, name in enumerate(day_names):
            if days_mask & (1 << i):
                days.append(name)
        return {
            "hour": state.get("hour"),
            "minute": state.get("minute"),
            "enabled": state.get("enabled"),
            "days_mask": days_mask,
            "days": ", ".join(days) if days else "None",
        }

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._instance.address)},
            manufacturer="ELK",
            model=self._instance._model or "BLEDOM",
            connections={(device_registry.CONNECTION_BLUETOOTH, self._instance.address)},
        )


class BLEDOMFirmwareVersionSensor(CoordinatorEntity[BLEDOMCoordinator], SensorEntity):
    """Firmware version sensor entity."""

    _attr_has_entity_name = True
    _attr_translation_key = "firmware_version"
    _attr_icon = "mdi:chip"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: BLEDOMCoordinator, bledomInstance: BLEDOMInstance, entry_id: str) -> None:
        super().__init__(coordinator)
        self._instance = bledomInstance
        self._attr_unique_id = f"{self._instance.address}_firmware_version"
        self._entry_id = entry_id

    @property
    def available(self) -> bool:
        return self._instance.firmware_version is not None

    @property
    def native_value(self) -> str | None:
        return self._instance.firmware_version

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._instance.address)},
            manufacturer="ELK",
            model=self._instance._model or "BLEDOM",
            connections={(device_registry.CONNECTION_BLUETOOTH, self._instance.address)},
        )


class BLEDOMConnectionStateSensor(CoordinatorEntity[BLEDOMCoordinator], SensorEntity):
    """Connection state sensor entity."""

    _attr_has_entity_name = True
    _attr_translation_key = "connection_state"
    _attr_icon = "mdi:bluetooth-connect"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: BLEDOMCoordinator, bledomInstance: BLEDOMInstance, entry_id: str) -> None:
        super().__init__(coordinator)
        self._instance = bledomInstance
        self._attr_unique_id = f"{self._instance.address}_connection_state"
        self._entry_id = entry_id

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> str:
        return self._instance.connection_state.value

    @property
    def extra_state_attributes(self) -> dict:
        return self._instance.connection_diagnostics

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._instance.address)},
            manufacturer="ELK",
            model=self._instance._model or "BLEDOM",
            connections={(device_registry.CONNECTION_BLUETOOTH, self._instance.address)},
        )
