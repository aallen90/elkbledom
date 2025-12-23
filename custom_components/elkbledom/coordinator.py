"""DataUpdateCoordinator for elkbledom integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .elkbledom import BLEDOMInstance

LOGGER = logging.getLogger(__name__)

# Polling interval - BLE devices don't need frequent polling
# State is also updated via notifications when available
SCAN_INTERVAL = timedelta(seconds=60)


class BLEDOMCoordinator(DataUpdateCoordinator[None]):
    """Coordinator to manage data updates for BLEDOM devices."""

    def __init__(self, hass: HomeAssistant, instance: BLEDOMInstance) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=f"BLEDOM {instance.name}",
            update_interval=SCAN_INTERVAL,
        )
        self.instance = instance

    async def _async_update_data(self) -> None:
        """Fetch data from the device."""
        try:
            await self.instance.update()
        except Exception as err:
            LOGGER.debug("Error updating %s: %s", self.instance.name, err)
            # Don't raise UpdateFailed for transient BLE errors
            # The device will reconnect on the next command
            pass
