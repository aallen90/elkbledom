from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers import device_registry

from .elkbledom import BLEDOMInstance
from .coordinator import BLEDOMCoordinator
from .const import DOMAIN, MIC_EFFECTS, MIC_EFFECTS_list

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
        BLEDOMMicEffect(coordinator, instance, config_entry.entry_id)
    ])

class BLEDOMMicEffect(CoordinatorEntity[BLEDOMCoordinator], RestoreEntity, SelectEntity):
    """Microphone Effect selector entity."""

    _attr_has_entity_name = True
    _attr_translation_key = "mic_effect"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = MIC_EFFECTS_list

    def __init__(self, coordinator: BLEDOMCoordinator, bledomInstance: BLEDOMInstance, entry_id: str) -> None:
        super().__init__(coordinator)
        self._instance = bledomInstance
        self._attr_unique_id = f"{self._instance.address}_mic_effect"
        self._current_option = MIC_EFFECTS_list[0]

    @property
    def available(self) -> bool:
        return self._instance.is_on is not None

    @property
    def current_option(self) -> str | None:
        return self._current_option

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

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if option in MIC_EFFECTS_list:
            effect_value = MIC_EFFECTS[option].value
            await self._instance.set_mic_effect(effect_value)
            self._current_option = option
            LOG.debug(f"Mic effect set to {option} (0x{effect_value:02x})")

    async def async_added_to_hass(self) -> None:
        """Restore previous state when entity is added to hass."""
        await super().async_added_to_hass()
        
        # Restore the last known mic effect
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state in MIC_EFFECTS_list:
                self._current_option = last_state.state
                LOG.debug(f"Restored mic effect for {self.name}: {self._current_option}")
            else:
                LOG.debug(f"Could not restore mic effect for {self.name}, using default")
