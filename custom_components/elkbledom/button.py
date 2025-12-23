from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
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
        BLEDOMSyncTimeButton(coordinator, instance, "Sync Time " + config_entry.data["name"], config_entry.entry_id)
    ])


class BLEDOMSyncTimeButton(CoordinatorEntity[BLEDOMCoordinator], ButtonEntity):
    """Sync Time button entity"""

    def __init__(self, coordinator: BLEDOMCoordinator, bledomInstance: BLEDOMInstance, attr_name: str, entry_id: str) -> None:
        super().__init__(coordinator)
        self._instance = bledomInstance
        self._attr_name = attr_name
        self._attr_unique_id = self._instance.address + "_sync_time"
        self._entry_id = entry_id

    @property
    def available(self):
        return self._instance.is_on is not None

    @property
    def name(self) -> str:
        return self._attr_name

    @property
    def unique_id(self) -> str:
        return self._attr_unique_id

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
