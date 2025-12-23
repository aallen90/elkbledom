from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BLEDOMCoordinator
from .elkbledom import BLEDOMInstance

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
        BLEDOMSyncTimeButton(coordinator, instance, config_entry.entry_id)
    ])


class BLEDOMSyncTimeButton(CoordinatorEntity[BLEDOMCoordinator], ButtonEntity):
    """Sync Time button entity."""

    _attr_has_entity_name = True
    _attr_translation_key = "sync_time"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: BLEDOMCoordinator, bledomInstance: BLEDOMInstance, entry_id: str) -> None:
        super().__init__(coordinator)
        self._instance = bledomInstance
        self._attr_unique_id = f"{self._instance.address}_sync_time"
        self._entry_id = entry_id

    @property
    def available(self) -> bool:
        return self._instance.is_on is not None

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

    async def async_press(self) -> None:
        """Handle the button press."""
        await self._instance.sync_time()
        LOG.debug("Synced time to device %s", self._instance.name)
