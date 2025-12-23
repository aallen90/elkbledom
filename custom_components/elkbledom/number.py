from __future__ import annotations

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory

from .elkbledom import BLEDOMInstance
from .coordinator import BLEDOMCoordinator
from .const import DOMAIN

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import device_registry
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry


import logging

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
        BLEDOMEffectSpeed(coordinator, instance, config_entry.entry_id),
        BLEDOMMicSensitivity(coordinator, instance, config_entry.entry_id)
    ])

class BLEDOMEffectSpeed(CoordinatorEntity[BLEDOMCoordinator], RestoreEntity, NumberEntity):
    """Effect Speed entity."""

    _attr_has_entity_name = True
    _attr_translation_key = "effect_speed"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 1
    _attr_native_max_value = 255
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: BLEDOMCoordinator, bledomInstance: BLEDOMInstance, entry_id: str) -> None:
        super().__init__(coordinator)
        self._instance = bledomInstance
        self._attr_unique_id = f"{self._instance.address}_effect_speed"
        self._effect_speed = 128  # Default to middle

    @property
    def available(self) -> bool:
        return self._instance.is_on is not None

    @property
    def native_value(self) -> int | None:
        # Sync with instance value
        if self._instance.effect_speed is not None:
            return self._instance.effect_speed
        return self._effect_speed

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={
                (DOMAIN, self._instance.address)
            },
            manufacturer="ELK",
            model=self._instance._model or "BLEDOM",
            connections={(device_registry.CONNECTION_BLUETOOTH,
                          self._instance.address)},
        )

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        await self._instance.set_effect_speed(int(value))
        self._effect_speed = int(value)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Restore previous state when entity is added to hass."""
        await super().async_added_to_hass()
        
        # Restore the last known effect speed
        if (last_state := await self.async_get_last_state()) is not None:
            try:
                self._effect_speed = int(float(last_state.state))
                LOG.debug(f"Restored effect speed for {self.name}: {self._effect_speed}")
            except (ValueError, TypeError):
                LOG.debug(f"Could not restore effect speed for {self.name}, using default")

class BLEDOMMicSensitivity(CoordinatorEntity[BLEDOMCoordinator], RestoreEntity, NumberEntity):
    """Microphone Sensitivity entity."""

    _attr_has_entity_name = True
    _attr_translation_key = "mic_sensitivity"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: BLEDOMCoordinator, bledomInstance: BLEDOMInstance, entry_id: str) -> None:
        super().__init__(coordinator)
        self._instance = bledomInstance
        self._attr_unique_id = f"{self._instance.address}_mic_sensitivity"
        self._mic_sensitivity = 50

    @property
    def available(self) -> bool:
        return self._instance.is_on is not None

    @property
    def native_value(self) -> int | None:
        return self._mic_sensitivity

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={
                (DOMAIN, self._instance.address)
            },
            manufacturer="ELK",
            model=self._instance._model or "BLEDOM",
            connections={(device_registry.CONNECTION_BLUETOOTH,
                          self._instance.address)},
        )

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        await self._instance.set_mic_sensitivity(int(value))
        self._mic_sensitivity = int(value)

    async def async_added_to_hass(self) -> None:
        """Restore previous state when entity is added to hass."""
        await super().async_added_to_hass()
        
        # Restore the last known mic sensitivity
        if (last_state := await self.async_get_last_state()) is not None:
            try:
                self._mic_sensitivity = int(float(last_state.state))
                LOG.debug(f"Restored mic sensitivity for {self.name}: {self._mic_sensitivity}")
            except (ValueError, TypeError):
                LOG.debug(f"Could not restore mic sensitivity for {self.name}, using default (50)")
        else:
            LOG.debug(f"No previous state found for {self.name}")