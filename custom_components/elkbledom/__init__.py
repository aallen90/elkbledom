from __future__ import annotations

import logging

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, ServiceCall

from .const import (
    CONF_BRIGHTNESS_MODE,
    CONF_DELAY,
    CONF_RESET,
    CONF_RGB_GAIN_B,
    CONF_RGB_GAIN_G,
    CONF_RGB_GAIN_R,
    DOMAIN,
)
from .coordinator import BLEDOMCoordinator
from .device import BLEDOMInstance

LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SWITCH,
    Platform.BUTTON,
    Platform.SENSOR,
]

# Service schema for RGBW channel control
SERVICE_SET_RGBW_CHANNELS = "set_rgbw_channels"
SET_RGBW_CHANNELS_SCHEMA = vol.Schema({
    vol.Required("entity_id"): cv.entity_id,
    vol.Optional("red", default=True): cv.boolean,
    vol.Optional("green", default=True): cv.boolean,
    vol.Optional("blue", default=True): cv.boolean,
    vol.Optional("white", default=True): cv.boolean,
    vol.Optional("mode", default="0"): vol.In(["0", "1", "2", "3", "4"]),  # 0=all, 1=RGB, 2=W, 3=CT, 4=laser
})

# Service for querying timer settings
SERVICE_QUERY_TIMER = "query_timer"
QUERY_TIMER_SCHEMA = vol.Schema({
    vol.Required("entity_id"): cv.entity_id,
})

# Service schemas for scheduler control
SERVICE_SET_SCHEDULE_ON = "set_schedule_on"
SERVICE_SET_SCHEDULE_OFF = "set_schedule_off"
SCHEDULE_SCHEMA = vol.Schema({
    vol.Required("entity_id"): cv.entity_id,
    vol.Required("time"): cv.time,
    vol.Optional("monday", default=True): cv.boolean,
    vol.Optional("tuesday", default=True): cv.boolean,
    vol.Optional("wednesday", default=True): cv.boolean,
    vol.Optional("thursday", default=True): cv.boolean,
    vol.Optional("friday", default=True): cv.boolean,
    vol.Optional("saturday", default=True): cv.boolean,
    vol.Optional("sunday", default=True): cv.boolean,
    vol.Optional("enabled", default=True): cv.boolean,
})

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ElkBLEDOM from a config entry."""
    reset = entry.options.get(CONF_RESET, None) or entry.data.get(CONF_RESET, None)
    delay = entry.options.get(CONF_DELAY, None) or entry.data.get(CONF_DELAY, None)
    mac = entry.options.get(CONF_MAC, None) or entry.data.get(CONF_MAC, None)
    rgb_gain_r = entry.options.get(CONF_RGB_GAIN_R, 1.0)
    rgb_gain_g = entry.options.get(CONF_RGB_GAIN_G, 1.0)
    rgb_gain_b = entry.options.get(CONF_RGB_GAIN_B, 1.0)
    brightness_mode = entry.options.get(CONF_BRIGHTNESS_MODE, "auto")
    LOGGER.debug("Config: Reset: %s, Delay: %s, Mac: %s", reset, delay, mac)

    instance = BLEDOMInstance(mac, reset, delay, hass)
    instance.set_rgb_gains(rgb_gain_r, rgb_gain_g, rgb_gain_b)
    instance.brightness_mode = brightness_mode

    coordinator = BLEDOMCoordinator(hass, instance)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "instance": instance,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    # Register RGBW service
    async def async_set_rgbw_channels(call: ServiceCall) -> None:
        """Handle the set_rgbw_channels service call."""
        # Note: entity_id is in call.data but we use the instance from this entry
        red = call.data.get("red", True)
        green = call.data.get("green", True)
        blue = call.data.get("blue", True)
        white = call.data.get("white", True)
        mode = int(call.data.get("mode", "0"))

        # Get the instance from entity_id
        # For simplicity, use the instance from this entry
        await instance.set_rgbw_channels(red, green, blue, white, mode)
        LOGGER.info("RGBW channels service called: R=%s G=%s B=%s W=%s mode=%d",
                    red, green, blue, white, mode)

    # Register service only once globally
    if not hass.services.has_service(DOMAIN, SERVICE_SET_RGBW_CHANNELS):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_RGBW_CHANNELS,
            async_set_rgbw_channels,
            schema=SET_RGBW_CHANNELS_SCHEMA,
        )

    # Helper to compute days bitmask from individual day booleans
    def _compute_days_bitmask(call: ServiceCall) -> int:
        """Convert individual day booleans to a bitmask."""
        days = 0
        if call.data.get("monday", True):
            days |= 0x01
        if call.data.get("tuesday", True):
            days |= 0x02
        if call.data.get("wednesday", True):
            days |= 0x04
        if call.data.get("thursday", True):
            days |= 0x08
        if call.data.get("friday", True):
            days |= 0x10
        if call.data.get("saturday", True):
            days |= 0x20
        if call.data.get("sunday", True):
            days |= 0x40
        return days

    # Register scheduler services
    async def async_set_schedule_on(call: ServiceCall) -> None:
        """Handle the set_schedule_on service call."""
        time_val = call.data["time"]
        hours = time_val.hour
        minutes = time_val.minute
        days = _compute_days_bitmask(call)
        enabled = call.data.get("enabled", True)
        await instance.set_scheduler_on(days, hours, minutes, enabled)
        LOGGER.info("Schedule ON set: %02d:%02d days=0x%02x enabled=%s",
                    hours, minutes, days, enabled)

    async def async_set_schedule_off(call: ServiceCall) -> None:
        """Handle the set_schedule_off service call."""
        time_val = call.data["time"]
        hours = time_val.hour
        minutes = time_val.minute
        days = _compute_days_bitmask(call)
        enabled = call.data.get("enabled", True)
        await instance.set_scheduler_off(days, hours, minutes, enabled)
        LOGGER.info("Schedule OFF set: %02d:%02d days=0x%02x enabled=%s",
                    hours, minutes, days, enabled)

    if not hass.services.has_service(DOMAIN, SERVICE_SET_SCHEDULE_ON):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_SCHEDULE_ON,
            async_set_schedule_on,
            schema=SCHEDULE_SCHEMA,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SET_SCHEDULE_OFF):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_SCHEDULE_OFF,
            async_set_schedule_off,
            schema=SCHEDULE_SCHEMA,
        )

    # Register query_timer service
    async def async_query_timer(call: ServiceCall) -> None:
        """Handle the query_timer service call."""
        result = await instance.query_timer()
        if result:
            LOGGER.info("Timer query result: ON=%s OFF=%s",
                        result.get("timer_on"), result.get("timer_off"))
        else:
            LOGGER.warning("Timer query returned no data")

    if not hass.services.has_service(DOMAIN, SERVICE_QUERY_TIMER):
        hass.services.async_register(
            DOMAIN,
            SERVICE_QUERY_TIMER,
            async_query_timer,
            schema=QUERY_TIMER_SCHEMA,
        )

    async def _async_stop(event: Event) -> None:
        """Close the connection."""
        await instance.stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop)
    )

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data["instance"].stop()
    return unload_ok

async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    data = hass.data[DOMAIN][entry.entry_id]
    instance = data["instance"]
    # Apply options live (avoid full reload for simple tuning).
    instance.set_rgb_gains(
        entry.options.get(CONF_RGB_GAIN_R, 1.0),
        entry.options.get(CONF_RGB_GAIN_G, 1.0),
        entry.options.get(CONF_RGB_GAIN_B, 1.0),
    )
    instance.brightness_mode = entry.options.get(CONF_BRIGHTNESS_MODE, "auto")
    if entry.title != instance.name:
        await hass.config_entries.async_reload(entry.entry_id)
