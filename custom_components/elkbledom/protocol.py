"""Protocol handlers for ELK-BLEDDM LED devices.

This module contains command builders and notification parsers for
the BLE protocol used by ELK-BLEDDM and compatible LED controllers.

Command Format: [0x7e, length/prefix, command, params..., checksum, 0xef]
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

LOGGER = logging.getLogger(__name__)

__all__ = [
    "build_color_cmd",
    "build_brightness_cmd",
    "build_effect_cmd",
    "build_mic_effect_cmd",
    "build_mic_sensitivity_cmd",
    "build_rgbw_channels_cmd",
    "build_rgb_order_cmd",
    "build_scheduler_cmd",
    "build_time_sync_cmd",
    "parse_notification",
    "NotificationData",
]


# Command byte constants
CMD_START = 0x7e
CMD_END = 0xef


@dataclass
class NotificationData:
    """Parsed notification data from device."""
    cmd_type: int
    raw_data: bytes
    # Power state
    is_on: bool | None = None
    # RGB color
    rgb_color: tuple[int, int, int] | None = None
    # Brightness (0-255)
    brightness: int | None = None
    # Timer ON settings
    timer_on_hour: int | None = None
    timer_on_minute: int | None = None
    timer_on_days: int | None = None
    timer_on_enabled: bool | None = None
    # Timer OFF settings
    timer_off_hour: int | None = None
    timer_off_minute: int | None = None
    timer_off_days: int | None = None
    timer_off_enabled: bool | None = None
    # Device time
    device_time: tuple[int, int, int, int] | None = None  # (hour, min, sec, weekday)


def build_color_cmd(r: int, g: int, b: int) -> list[int]:
    """Build RGB color command.

    Args:
        r: Red value (0-255)
        g: Green value (0-255)
        b: Blue value (0-255)

    Returns:
        9-byte command array
    """
    return [0x7e, 0x07, 0x05, 0x03, r & 0xff, g & 0xff, b & 0xff, 0x10, 0xef]


def build_brightness_cmd(brightness: int) -> list[int]:
    """Build brightness command.

    Args:
        brightness: Brightness level (0-100)

    Returns:
        9-byte command array
    """
    level = max(0, min(100, brightness))
    return [0x7e, 0x04, 0x01, level, 0xff, 0xff, 0xff, 0x00, 0xef]


def build_effect_cmd(effect_id: int, template: list[int]) -> list[int]:
    """Build effect command from template.

    Args:
        effect_id: Effect ID (0x80-0x9F typically)
        template: Command template from ModelConfig.effect_cmd

    Returns:
        Command array with effect_id inserted
    """
    cmd = list(template)
    if len(cmd) >= 4:
        cmd[3] = effect_id & 0xff
    return cmd


def build_effect_speed_cmd(speed: int, template: list[int]) -> list[int]:
    """Build effect speed command from template.

    Args:
        speed: Speed value (0-255, higher = slower typically)
        template: Command template from ModelConfig.effect_speed_cmd

    Returns:
        Command array with speed inserted
    """
    cmd = list(template)
    if len(cmd) >= 4:
        cmd[3] = speed & 0xff
    return cmd


def build_mic_effect_cmd(effect_id: int) -> list[int]:
    """Build microphone effect command.

    Args:
        effect_id: Mic effect ID (0x00-0x0F)

    Returns:
        9-byte command array
    """
    return [0x7e, 0x00, 0x06, effect_id & 0x0f, 0xff, 0xff, 0xff, 0x00, 0xef]


def build_mic_sensitivity_cmd(sensitivity: int) -> list[int]:
    """Build microphone sensitivity command.

    Args:
        sensitivity: Sensitivity level (0-100)

    Returns:
        9-byte command array
    """
    level = max(0, min(100, sensitivity))
    return [0x7e, 0x00, 0x07, level, 0xff, 0xff, 0xff, 0x00, 0xef]


def build_mic_enable_cmd(enable: bool) -> list[int]:
    """Build microphone enable/disable command.

    Args:
        enable: True to enable, False to disable

    Returns:
        9-byte command array
    """
    return [0x7e, 0x00, 0x06, 0x01 if enable else 0x00, 0xff, 0xff, 0xff, 0x00, 0xef]


def build_rgbw_channels_cmd(
    r_on: bool = True,
    g_on: bool = True,
    b_on: bool = True,
    w_on: bool = True,
    mode: int = 0
) -> list[int]:
    """Build RGBW channel control command.

    Args:
        r_on: Enable red channel
        g_on: Enable green channel
        b_on: Enable blue channel
        w_on: Enable white channel
        mode: Operating mode (0=all, 1=RGB, 2=W, 3=CT, 4=laser)

    Returns:
        9-byte command array
    """
    r_val = 0x01 if r_on else 0x00
    g_val = 0x01 if g_on else 0x00
    b_val = 0x01 if b_on else 0x00
    w_val = 0x01 if w_on else 0x00
    return [0x7e, 0x00, 0x80, r_val, g_val, b_val, w_val, mode & 0x0f, 0xef]


def build_rgb_order_cmd(r_position: int, g_position: int, b_position: int) -> list[int]:
    """Build RGB channel order command.

    Args:
        r_position: Position of red channel (0-2)
        g_position: Position of green channel (0-2)
        b_position: Position of blue channel (0-2)

    Returns:
        9-byte command array
    """
    return [0x7e, 0x06, 0x81, r_position & 0x03, g_position & 0x03, b_position & 0x03, 0xff, 0x00, 0xef]


def build_scheduler_cmd(
    mode: int,  # 0 = turn on, 1 = turn off
    hours: int,
    minutes: int,
    days: int,
    enabled: bool
) -> list[int]:
    """Build scheduler command.

    Args:
        mode: 0 for turn-on schedule, 1 for turn-off schedule
        hours: Hour (0-23)
        minutes: Minute (0-59)
        days: Day bitmask (bit0=Mon, bit1=Tue, ..., bit6=Sun)
        enabled: Whether schedule is active

    Returns:
        9-byte command array
    """
    days_with_flag = (days & 0x7f) | (0x80 if enabled else 0x00)
    return [0x7e, 0x00, 0x82, hours & 0x1f, minutes & 0x3f, 0x00, mode & 0x01, days_with_flag, 0xef]


def build_time_sync_cmd(dt: datetime | None = None) -> list[int]:
    """Build time synchronization command.

    Args:
        dt: Datetime to sync, or None for current time

    Returns:
        9-byte command array
    """
    if dt is None:
        dt = datetime.now()

    hour = dt.hour
    minute = dt.minute
    second = dt.second
    # Python weekday: 0=Monday, but device expects 1=Monday
    weekday = dt.weekday() + 1

    return [0x7e, 0x07, 0x83, hour, minute, second, weekday, 0xff, 0xef]


def parse_notification(data: bytes | bytearray) -> NotificationData | None:
    """Parse notification data from device.

    Args:
        data: Raw notification bytes

    Returns:
        NotificationData with parsed fields, or None if invalid
    """
    if len(data) < 3 or data[0] != CMD_START:
        return None

    cmd_type = data[2]
    result = NotificationData(cmd_type=cmd_type, raw_data=bytes(data))

    # Timer response (0x85) - contains both on and off schedules
    # Format: 7e 09 85 H1 M1 W1 H2 M2 W2
    if cmd_type == 0x85 and len(data) >= 9:
        result.timer_on_hour = data[3]
        result.timer_on_minute = data[4]
        result.timer_on_days = data[5] & 0x7f
        result.timer_on_enabled = bool(data[5] & 0x80)
        result.timer_off_hour = data[6]
        result.timer_off_minute = data[7]
        result.timer_off_days = data[8] & 0x7f
        result.timer_off_enabled = bool(data[8] & 0x80)
        return result

    # Timer status response (0x82) - single timer confirmation
    # Format: 7e 08 82 H M S mode days ef
    if cmd_type == 0x82 and len(data) >= 9 and data[8] == CMD_END:
        hour, minute = data[3], data[4]
        mode = data[6]  # 0 = on timer, 1 = off timer
        days_enabled = data[7]
        days = days_enabled & 0x7f
        enabled = bool(days_enabled & 0x80)
        if mode == 0:
            result.timer_on_hour = hour
            result.timer_on_minute = minute
            result.timer_on_days = days
            result.timer_on_enabled = enabled
        else:
            result.timer_off_hour = hour
            result.timer_off_minute = minute
            result.timer_off_days = days
            result.timer_off_enabled = enabled
        return result

    # Time sync response (0x83) - device time confirmation
    # Format: 7e 07 83 H M S wd ff ef
    if cmd_type == 0x83 and len(data) >= 9:
        hour, minute, second, weekday = data[3], data[4], data[5], data[6]
        result.device_time = (hour, minute, second, weekday)
        return result

    # Status response (0x01) - power and color state
    if cmd_type == 0x01 and len(data) >= 9 and data[8] == CMD_END:
        power_state = data[3]
        if power_state in [0x23, 0xf0, 0x01]:
            result.is_on = True
        elif power_state in [0x24, 0x00]:
            result.is_on = False

        # Try to parse RGB color if available
        if len(data) >= 8:
            r, g, b = data[4], data[5], data[6]
            if r != 0xff or g != 0xff or b != 0xff:
                result.rgb_color = (r, g, b)

        # Brightness might be in data[7]
        if len(data) >= 8 and data[7] != 0xff:
            brightness_percent = data[7]
            result.brightness = int(brightness_percent * 255 / 100)

        return result

    # Return basic result for unknown commands
    return result
