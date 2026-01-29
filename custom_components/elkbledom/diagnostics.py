"""Diagnostics support for ElkBLEDOM."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = hass.data[DOMAIN].get(entry.entry_id, {})
    instance = data.get("instance")

    diagnostics: dict[str, Any] = {
        "config_entry": {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "data": {
                "name": entry.data.get("name"),
                # Redact MAC address for privacy (show last 4 chars only)
                "mac": f"**:**:**:**:{entry.data.get('mac', '')[-5:]}" if entry.data.get("mac") else None,
            },
            "options": dict(entry.options),
        },
    }

    if instance:
        diagnostics["device"] = {
            "model": instance.model_name,
            "address_redacted": f"**:**:**:**:{instance.address[-5:]}" if instance.address else None,
            "is_connected": instance._client.is_connected if instance._client else False,
            "is_on": instance.is_on,
            "brightness": instance.brightness,
            "rgb_color": instance.rgb_color,
            "color_temp_kelvin": instance.color_temp_kelvin,
            "effect": instance.effect,
            "effect_speed": instance.effect_speed,
            "brightness_mode": instance._brightness_mode,
        }

        diagnostics["connection"] = {
            "rssi": instance.rssi,
            "reset_on_connect": instance.reset,
            "disconnect_delay": instance._delay,
            "write_uuid": instance._write_uuid if hasattr(instance, "_write_uuid") else None,
            "read_uuid": instance._read_uuid if hasattr(instance, "_read_uuid") else None,
        }

        diagnostics["rgb_calibration"] = {
            "gain_r": instance._rgb_gain_r,
            "gain_g": instance._rgb_gain_g,
            "gain_b": instance._rgb_gain_b,
        }

    return diagnostics
