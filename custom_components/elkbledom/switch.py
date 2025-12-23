from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers import device_registry

from .elkbledom import BLEDOMInstance
from .coordinator import BLEDOMCoordinator
from .const import DOMAIN

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
        BLEDOMMicSwitch(coordinator, instance, config_entry.entry_id)
    ])

class BLEDOMMicSwitch(CoordinatorEntity[BLEDOMCoordinator], RestoreEntity, SwitchEntity):
    """Microphone Enable/Disable switch entity."""

    _attr_has_entity_name = True
    _attr_translation_key = "mic_enable"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: BLEDOMCoordinator, bledomInstance: BLEDOMInstance, entry_id: str) -> None:
        super().__init__(coordinator)
        self._instance = bledomInstance
        self._attr_unique_id = f"{self._instance.address}_mic_enable"
        self._is_on = False

    @property
    def available(self) -> bool:
        return self._instance.is_on is not None

    @property
    def is_on(self) -> bool:
        return self._is_on

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

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the microphone on."""
        await self._instance.enable_mic()
        self._is_on = True
        LOG.debug(f"Microphone enabled for {self.name}")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the microphone off."""
        await self._instance.disable_mic()
        self._is_on = False
        LOG.debug(f"Microphone disabled for {self.name}")

    async def async_added_to_hass(self) -> None:
        """Restore previous state when entity is added to hass."""
        await super().async_added_to_hass()
        
        # Restore the last known mic state
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state == "on":
                self._is_on = True
                LOG.debug(f"Restored mic state for {self.name}: ON")
            elif last_state.state == "off":
                self._is_on = False
                LOG.debug(f"Restored mic state for {self.name}: OFF")
        else:
            LOG.debug(f"No previous mic state found for {self.name}, defaulting to OFF")
