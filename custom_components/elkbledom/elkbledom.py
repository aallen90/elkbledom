import asyncio
import json
import logging
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar, cast

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.backends.service import BleakGATTServiceCollection
from bleak.exc import BleakDBusError
from bleak_retry_connector import BLEAK_RETRY_EXCEPTIONS as BLEAK_EXCEPTIONS
from bleak_retry_connector import (
    BleakClientWithServiceCache,
    BleakNotFoundError,
    establish_connection,
)
from homeassistant.components.bluetooth import (
    async_ble_device_from_address,
    async_discovered_service_info,
)
from homeassistant.exceptions import ConfigEntryNotReady

LOGGER = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """Configuration for a specific LED strip model."""
    name: str
    write_uuid: str
    read_uuid: str
    turn_on_cmd: list[int]
    turn_off_cmd: list[int]
    white_cmd: list[int]
    effect_speed_cmd: list[int]
    effect_cmd: list[int]
    color_temp_cmd: list[int]
    min_color_temp_k: int = 1800
    max_color_temp_k: int = 7000
    # Default RGB gains for better white balance (1.0 = no adjustment)
    default_rgb_gains: tuple[float, float, float] = (1.0, 1.0, 1.0)
    # Alternative commands for hardware variants (e.g., ELK-BLEDDM has 0x00 vs 0x04)
    alt_turn_on_cmd: list[int] | None = None
    alt_turn_off_cmd: list[int] | None = None


# Model database - each model has its own configuration
MODEL_DB: dict[str, ModelConfig] = {
    "ELK-BLEDDM": ModelConfig(
        name="ELK-BLEDDM",
        write_uuid="0000fff3-0000-1000-8000-00805f9b34fb",
        read_uuid="0000fff4-0000-1000-8000-00805f9b34fb",
        turn_on_cmd=[0x7e, 0x04, 0x04, 0xf0, 0x00, 0x01, 0xff, 0x00, 0xef],
        turn_off_cmd=[0x7e, 0x04, 0x04, 0x00, 0x00, 0x00, 0xff, 0x00, 0xef],
        white_cmd=[0x7e, 0x00, 0x01, 0xbb, 0x00, 0x00, 0x00, 0x00, 0xef],
        effect_speed_cmd=[0x7e, 0x00, 0x02, 0xbb, 0x00, 0x00, 0x00, 0x00, 0xef],
        effect_cmd=[0x7e, 0x00, 0x03, 0xbb, 0x03, 0x00, 0x00, 0x00, 0xef],
        color_temp_cmd=[0x7e, 0x00, 0x05, 0x02, 0xbb, 0xbb, 0x00, 0x00, 0xef],
        default_rgb_gains=(1.00, 0.88, 0.38),
        # Some ELK-BLEDDM units use 0x00 instead of 0x04 as the second byte
        alt_turn_on_cmd=[0x7e, 0x00, 0x04, 0xf0, 0x00, 0x01, 0xff, 0x00, 0xef],
        alt_turn_off_cmd=[0x7e, 0x00, 0x04, 0x00, 0x00, 0x00, 0xff, 0x00, 0xef],
    ),
    "ELK-BLE": ModelConfig(
        name="ELK-BLE",
        write_uuid="0000fff3-0000-1000-8000-00805f9b34fb",
        read_uuid="0000fff4-0000-1000-8000-00805f9b34fb",
        turn_on_cmd=[0x7e, 0x00, 0x04, 0xf0, 0x00, 0x01, 0xff, 0x00, 0xef],
        turn_off_cmd=[0x7e, 0x00, 0x04, 0x00, 0x00, 0x00, 0xff, 0x00, 0xef],
        white_cmd=[0x7e, 0x00, 0x01, 0xbb, 0x00, 0x00, 0x00, 0x00, 0xef],
        effect_speed_cmd=[0x7e, 0x00, 0x02, 0xbb, 0x00, 0x00, 0x00, 0x00, 0xef],
        effect_cmd=[0x7e, 0x00, 0x03, 0xbb, 0x03, 0x00, 0x00, 0x00, 0xef],
        color_temp_cmd=[0x7e, 0x00, 0x05, 0x02, 0xbb, 0xbb, 0x00, 0x00, 0xef],
    ),
    "LEDBLE": ModelConfig(
        name="LEDBLE",
        write_uuid="0000ffe1-0000-1000-8000-00805f9b34fb",
        read_uuid="0000ffe2-0000-1000-8000-00805f9b34fb",
        turn_on_cmd=[0x7e, 0x00, 0x04, 0x01, 0x00, 0x00, 0x00, 0x00, 0xef],
        turn_off_cmd=[0x7e, 0x00, 0x04, 0x00, 0x00, 0x00, 0xff, 0x00, 0xef],
        white_cmd=[0x7e, 0x00, 0x01, 0xbb, 0x00, 0x00, 0x00, 0x00, 0xef],
        effect_speed_cmd=[0x7e, 0x00, 0x02, 0xbb, 0x00, 0x00, 0x00, 0x00, 0xef],
        effect_cmd=[0x7e, 0x00, 0x03, 0xbb, 0x03, 0x00, 0x00, 0x00, 0xef],
        color_temp_cmd=[0x7e, 0x00, 0x05, 0x02, 0xbb, 0xbb, 0x00, 0x00, 0xef],
    ),
    "MELK-OG10": ModelConfig(
        name="MELK-OG10",
        write_uuid="0000fff3-0000-1000-8000-00805f9b34fb",
        read_uuid="0000fff4-0000-1000-8000-00805f9b34fb",
        turn_on_cmd=[0x7e, 0x07, 0x04, 0xff, 0x00, 0x01, 0x02, 0x01, 0xef],
        turn_off_cmd=[0x7e, 0x07, 0x04, 0x00, 0x00, 0x00, 0x02, 0x00, 0xef],
        white_cmd=[0x7e, 0x07, 0x05, 0x01, 0xbb, 0xff, 0x02, 0x01],
        effect_speed_cmd=[0x7e, 0x04, 0x02, 0xbb, 0xff, 0xff, 0xff, 0x00, 0xef],
        effect_cmd=[0x7e, 0x05, 0x03, 0xbb, 0x06, 0xff, 0xff, 0x00, 0xef],
        color_temp_cmd=[0x7e, 0x06, 0x05, 0x02, 0xbb, 0xbb, 0xff, 0x08, 0xef],
    ),
    "MELK": ModelConfig(
        name="MELK",
        write_uuid="0000fff3-0000-1000-8000-00805f9b34fb",
        read_uuid="0000fff4-0000-1000-8000-00805f9b34fb",
        turn_on_cmd=[0x7e, 0x00, 0x04, 0x01, 0x00, 0x00, 0x00, 0x00, 0xef],
        turn_off_cmd=[0x7e, 0x00, 0x04, 0x00, 0x00, 0x00, 0xff, 0x00, 0xef],
        white_cmd=[0x7e, 0x00, 0x01, 0xbb, 0x00, 0x00, 0x00, 0x00, 0xef],
        effect_speed_cmd=[0x7e, 0x04, 0x02, 0xbb, 0xff, 0xff, 0xff, 0x00, 0xef],
        effect_cmd=[0x7e, 0x05, 0x03, 0xbb, 0x06, 0xff, 0xff, 0x00, 0xef],
        color_temp_cmd=[0x7e, 0x06, 0x05, 0x02, 0xbb, 0xbb, 0xff, 0x08, 0xef],
    ),
    "ELK-BULB2": ModelConfig(
        name="ELK-BULB2",
        write_uuid="0000fff3-0000-1000-8000-00805f9b34fb",
        read_uuid="0000fff4-0000-1000-8000-00805f9b34fb",
        turn_on_cmd=[0x7e, 0x00, 0x04, 0xf0, 0x00, 0x01, 0xff, 0x00, 0xef],
        turn_off_cmd=[0x7e, 0x00, 0x04, 0x01, 0x00, 0x00, 0x00, 0x00, 0xef],
        white_cmd=[0x7e, 0x00, 0x01, 0xbb, 0x00, 0x00, 0x00, 0x00, 0xef],
        effect_speed_cmd=[0x7e, 0x00, 0x02, 0xbb, 0x00, 0x00, 0x00, 0x00, 0xef],
        effect_cmd=[0x7e, 0x00, 0x03, 0xbb, 0x03, 0x00, 0x00, 0x00, 0xef],
        color_temp_cmd=[0x7e, 0x00, 0x05, 0x02, 0xbb, 0xbb, 0x00, 0x00, 0xef],
    ),
    "ELK-BULB": ModelConfig(
        name="ELK-BULB",
        write_uuid="0000fff3-0000-1000-8000-00805f9b34fb",
        read_uuid="0000fff4-0000-1000-8000-00805f9b34fb",
        turn_on_cmd=[0x7e, 0x00, 0x04, 0x01, 0x00, 0x00, 0x00, 0x00, 0xef],
        turn_off_cmd=[0x7e, 0x00, 0x04, 0x00, 0x00, 0x00, 0xff, 0x00, 0xef],
        white_cmd=[0x7e, 0x00, 0x01, 0xbb, 0x00, 0x00, 0x00, 0x00, 0xef],
        effect_speed_cmd=[0x7e, 0x00, 0x02, 0xbb, 0x00, 0x00, 0x00, 0x00, 0xef],
        effect_cmd=[0x7e, 0x00, 0x03, 0xbb, 0x03, 0x00, 0x00, 0x00, 0xef],
        color_temp_cmd=[0x7e, 0x00, 0x05, 0x02, 0xbb, 0xbb, 0x00, 0x00, 0xef],
    ),
    "ELK-LAMPL": ModelConfig(
        name="ELK-LAMPL",
        write_uuid="0000fff3-0000-1000-8000-00805f9b34fb",
        read_uuid="0000fff4-0000-1000-8000-00805f9b34fb",
        turn_on_cmd=[0x7e, 0x00, 0x04, 0x01, 0x00, 0x00, 0x00, 0x00, 0xef],
        turn_off_cmd=[0x7e, 0x00, 0x04, 0x00, 0x00, 0x00, 0xff, 0x00, 0xef],
        white_cmd=[0x7e, 0x00, 0x01, 0xbb, 0x00, 0x00, 0x00, 0x00, 0xef],
        effect_speed_cmd=[0x7e, 0x00, 0x02, 0xbb, 0x00, 0x00, 0x00, 0x00, 0xef],
        effect_cmd=[0x7e, 0x00, 0x03, 0xbb, 0x03, 0x00, 0x00, 0x00, 0xef],
        color_temp_cmd=[0x7e, 0x00, 0x05, 0x02, 0xbb, 0xbb, 0x00, 0x00, 0xef],
    ),
}


def get_supported_name_prefixes() -> list[str]:
    """Get list of supported device name prefixes."""
    return list(MODEL_DB.keys())


def get_all_characteristic_uuids() -> tuple[set[str], set[str]]:
    """Get unique read and write characteristic UUIDs from all models.

    Returns:
        Tuple of (read_uuids, write_uuids) as sets.
    """
    read_uuids = {m.read_uuid for m in MODEL_DB.values()}
    write_uuids = {m.write_uuid for m in MODEL_DB.values()}
    return read_uuids, write_uuids

# Query/Status commands to try for different LED strip models
# Format: [command_bytes, description]
QUERY_COMMANDS = [
    # Standard ELK-BLEDOM commands
    ([0x7e, 0x00, 0x01, 0xfa, 0x00, 0x00, 0x00, 0x00, 0xef], "Standard status query"),
    ([0x7e, 0x00, 0x10, 0x00, 0x00, 0x00, 0x00, 0x00, 0xef], "Alternative query v1"),
    ([0x7e, 0x00, 0x81, 0x00, 0x00, 0x00, 0x00, 0x00, 0xef], "Status query 0x81"),
    ([0x7e, 0x00, 0x82, 0x00, 0x00, 0x00, 0x00, 0x00, 0xef], "Status query 0x82"),
    ([0x7e, 0x00, 0x83, 0x00, 0x00, 0x00, 0x00, 0x00, 0xef], "Status query 0x83"),

    # Short format commands
    ([0xef, 0x01, 0x77], "Short query v1"),
    ([0x7e, 0x00, 0x10], "Short query v2"),
    ([0x7e, 0x10], "Minimal query"),
    ([0x25, 0x00], "Minimal query 2"),
    ([0x25, 0x02], "Minimal query 3"),

    # MELK specific commands
    ([0x7e, 0x04, 0x01, 0x00, 0xff, 0x00, 0xff, 0x00, 0xef], "MELK status query"),
    ([0x7e, 0x07, 0x01, 0x00, 0x00, 0x00, 0x02, 0x00, 0xef], "MELK query v2"),

    # Alternative long format
    ([0x7e, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xef], "Get all status"),
    ([0x7e, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0xef], "Status cmd 0x01"),
    ([0x7e, 0x04, 0x00, 0x00, 0x00, 0x00, 0xff, 0x00, 0xef], "Power status query"),

    # LEDBLE specific
    ([0x7e, 0x00, 0x04, 0xfa, 0x00, 0x00, 0x00, 0x00, 0xef], "LEDBLE status"),
    ([0xcc, 0x23, 0x33], "LEDBLE short status"),

    # Other variants found in wild
    ([0xaa, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x55], "Variant header 0xaa"),
    ([0x7e, 0x00, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00, 0xef], "Query cmd 0x05"),

    # ========== 30 COMANDOS ADICIONALES ==========

    # Variantes 0x7e con diferentes bytes de comando (0x02-0x0f)
    ([0x7e, 0x00, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0xef], "Query cmd 0x02"),
    ([0x7e, 0x00, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0xef], "Query cmd 0x03"),
    ([0x7e, 0x00, 0x06, 0x00, 0x00, 0x00, 0x00, 0x00, 0xef], "Query cmd 0x06"),
    ([0x7e, 0x00, 0x07, 0x00, 0x00, 0x00, 0x00, 0x00, 0xef], "Query cmd 0x07"),
    ([0x7e, 0x00, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0xef], "Query cmd 0x08"),
    ([0x7e, 0x00, 0x09, 0x00, 0x00, 0x00, 0x00, 0x00, 0xef], "Query cmd 0x09"),
    ([0x7e, 0x00, 0x0a, 0x00, 0x00, 0x00, 0x00, 0x00, 0xef], "Query cmd 0x0a"),
    ([0x7e, 0x00, 0x0b, 0x00, 0x00, 0x00, 0x00, 0x00, 0xef], "Query cmd 0x0b"),
    ([0x7e, 0x00, 0x0c, 0x00, 0x00, 0x00, 0x00, 0x00, 0xef], "Query cmd 0x0c"),
    ([0x7e, 0x00, 0x0d, 0x00, 0x00, 0x00, 0x00, 0x00, 0xef], "Query cmd 0x0d"),

    # Comandos con segundo byte variable (prefijo alternativo)
    ([0x7e, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xef], "Query prefix 0x01"),
    ([0x7e, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xef], "Query prefix 0x02"),
    ([0x7e, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xef], "Query prefix 0x03"),
    ([0x7e, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xef], "Query prefix 0x05"),
    ([0x7e, 0x06, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xef], "Query prefix 0x06"),
    ([0x7e, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xef], "Query prefix 0x08"),
    ([0x7e, 0x09, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xef], "Query prefix 0x09"),

    # Comandos cortos con diferentes protocolos
    ([0xef, 0x01], "Minimal EF query"),
    ([0xef, 0x77], "EF query 0x77"),
    ([0xef, 0x00], "EF query 0x00"),
    ([0x10, 0x00], "Query 0x10 0x00"),
    ([0x10, 0x01], "Query 0x10 0x01"),
    ([0xaa, 0x00], "AA protocol query"),
    ([0xbb, 0x00, 0x00], "BB protocol query"),

    # Comandos tipo checksum/CRC diferentes
    ([0x7e, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0xff], "Query end 0xff"),
    ([0x7e, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0xfe], "Query end 0xfe"),
    ([0x7e, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0xee], "Query end 0xee"),

    # Comandos tipo "ping" o "hello"
    ([0xff, 0x00, 0x00], "Ping command"),
    ([0x00, 0x00, 0x00], "Null query"),
    ([0x01], "Single byte query"),
    ([0xff], "Single 0xFF query"),
]

DEFAULT_ATTEMPTS = 3
BLEAK_BACKOFF_TIME = 0.25
RETRY_BACKOFF_EXCEPTIONS = (BleakDBusError,)
WrapFuncType = TypeVar("WrapFuncType", bound=Callable[..., Any])


def retry_bluetooth_connection_error(func: WrapFuncType) -> WrapFuncType:
    """Define a wrapper to retry on bleak error.

    The accessory is allowed to disconnect us any time so
    we need to retry the operation.
    """

    async def _async_wrap_retry_bluetooth_connection_error(
        self: "BLEDOMInstance", *args: Any, **kwargs: Any
    ) -> Any:
        attempts = DEFAULT_ATTEMPTS
        max_attempts = attempts - 1

        for attempt in range(attempts):
            try:
                return await func(self, *args, **kwargs)
            except BleakNotFoundError:
                # The lock cannot be found so there is no
                # point in retrying.
                raise
            except RETRY_BACKOFF_EXCEPTIONS as err:
                if attempt >= max_attempts:
                    LOGGER.debug("%s: %s error calling %s, reach max attempts (%s/%s)",self.name,type(err),func,attempt,max_attempts,exc_info=True,)
                    raise
                LOGGER.debug("%s: %s error calling %s, backing off %ss, retrying (%s/%s)...",self.name,type(err),func,BLEAK_BACKOFF_TIME,attempt,max_attempts,exc_info=True,)
                await asyncio.sleep(BLEAK_BACKOFF_TIME)
            except BLEAK_EXCEPTIONS as err:
                if attempt >= max_attempts:
                    LOGGER.debug("%s: %s error calling %s, reach max attempts (%s/%s): %s",self.name,type(err),func,attempt,max_attempts,err,exc_info=True,)
                    raise
                LOGGER.debug("%s: %s error calling %s, retrying  (%s/%s)...: %s",self.name,type(err),func,attempt,max_attempts,err,exc_info=True,)

    return cast(WrapFuncType, _async_wrap_retry_bluetooth_connection_error)

class CharacteristicMissingError(Exception):
    """Raised when a characteristic is missing."""
class DeviceData:
    def __init__(self, hass, discovery_info):
        self._discovery = discovery_info
        self._supported = any(self._discovery.name.lower().startswith(prefix.lower()) for prefix in MODEL_DB.keys())
        self._address = self._discovery.address
        self._name = self._discovery.name
        self._rssi = self._discovery.rssi
        self._hass = hass
        self._bledevice = async_ble_device_from_address(hass, self._address)

    @property
    def is_supported(self) -> bool:
        return self._supported

    @property
    def address(self):
        return self._address

    @property
    def get_device_name(self):
        return self._name

    @property
    def name(self):
        return self._name

    @property
    def rssi(self):
        return self._rssi

    def bledevice(self) -> BLEDevice:
        return self._bledevice

    def update_device(self):
        """Update device info from BLE discovery."""
        for discovery_info in async_discovered_service_info(self._hass):
            if discovery_info.address == self._address:
                self._rssi = discovery_info.rssi


class BLEDOMInstance:
    def __init__(self, address, reset: bool, delay: int, hass) -> None:
        self.loop = asyncio.get_running_loop()
        self._address = address
        self._reset = reset
        self._delay = delay
        self._hass = hass
        self._device: BLEDevice | None = None
        self._device_data: DeviceData | None = None
        self._connect_lock: asyncio.Lock = asyncio.Lock()
        self._client: BleakClientWithServiceCache | None = None
        self._disconnect_timer: asyncio.TimerHandle | None = None
        self._cached_services: BleakGATTServiceCollection | None = None
        self._expected_disconnect = False
        self._is_on = None
        self._rgb_color = None
        self._brightness = 255
        self._effect = None
        self._effect_speed = 128  # Default medium speed (0-255 range)
        self._color_temp_kelvin = None
        self._mic_effect = None
        self._mic_sensitivity = 50
        self._mic_enabled = False
        self._write_uuid = None
        self._read_uuid = None
        self._turn_on_cmd = None
        self._turn_off_cmd = None
        self._white_cmd = None
        self._effect_speed_cmd = None
        self._effect_cmd = None
        self._color_temp_cmd = None
        self._color_temp = None
        self._max_color_temp_kelvin = None
        self._min_color_temp_kelvin = None
        self._model = None
        self._working_query_cmd = None  # Command that works for this device
        self._query_detection_done = False  # Flag to avoid retesting
        self._notification_received = False  # Flag to detect responses
        self._bleddm_variant_checked = False  # ELK-BLEDDM variant detection done

        # Per-device RGB calibration gains (applied to set_color RGB writes only)
        self._rgb_gain_r: float = 1.0
        self._rgb_gain_g: float = 1.0
        self._rgb_gain_b: float = 1.0

        # Brightness mode: "auto", "rgb", or "native"
        self._brightness_mode: str = "auto"

        try:
            self._device = async_ble_device_from_address(hass, self._address)
        except (Exception) as error:
            LOGGER.error("Error getting device: %s", error)

        for discovery_info in async_discovered_service_info(hass):
            if discovery_info.address == address:
                devicedata = DeviceData(hass, discovery_info)
                LOGGER.debug("device %s: %s %s",devicedata.name, devicedata.address, devicedata.rssi)
                if devicedata.is_supported:
                    self._device_data = devicedata

        if not self._device:
            raise ConfigEntryNotReady(f"You need to add bluetooth integration (https://www.home-assistant.io/integrations/bluetooth) or couldn't find a nearby device with address: {address}")

        self._detect_model()

        # Apply default RGB gains from MODEL_DB if defined
        model_config = MODEL_DB.get(self._model) if self._model else None
        if model_config and model_config.default_rgb_gains != (1.0, 1.0, 1.0):
            r, g, b = model_config.default_rgb_gains
            self.set_rgb_gains(r, g, b)
        LOGGER.debug('Model information for device %s : ModelNo %s, Turn on cmd %s, Turn off cmd %s, White cmd %s, rssi %s', self.name, self._model, self._turn_on_cmd, self._turn_off_cmd, self._white_cmd, self.rssi)

    def _detect_model(self):
        """Detect the LED model from the device name and load its configuration."""
        if self._device is None or self._device.name is None:
            LOGGER.warning("Device or device name is None, using default configuration")
            first_config = next(iter(MODEL_DB.values()))
            self._model = first_config.name
            self._turn_on_cmd = list(first_config.turn_on_cmd)
            self._turn_off_cmd = list(first_config.turn_off_cmd)
            self._white_cmd = list(first_config.white_cmd)
            self._effect_speed_cmd = list(first_config.effect_speed_cmd)
            self._effect_cmd = list(first_config.effect_cmd)
            self._color_temp_cmd = list(first_config.color_temp_cmd)
            self._max_color_temp_kelvin = first_config.max_color_temp_k
            self._min_color_temp_kelvin = first_config.min_color_temp_k
            return None
        device_name_lower = self._device.name.lower()

        for name, config in MODEL_DB.items():
            if device_name_lower.startswith(name.lower()):
                self._model = name
                self._turn_on_cmd = list(config.turn_on_cmd)
                self._turn_off_cmd = list(config.turn_off_cmd)
                self._white_cmd = list(config.white_cmd)
                self._effect_speed_cmd = list(config.effect_speed_cmd)
                self._effect_cmd = list(config.effect_cmd)
                self._color_temp_cmd = list(config.color_temp_cmd)
                self._max_color_temp_kelvin = config.max_color_temp_k
                self._min_color_temp_kelvin = config.min_color_temp_k
                return name

        # Fallback to first model if no match (shouldn't happen if discovery is working)
        LOGGER.warning("Unknown device model '%s', using default configuration", self.name)
        first_config = next(iter(MODEL_DB.values()))
        self._model = first_config.name
        self._turn_on_cmd = list(first_config.turn_on_cmd)
        self._turn_off_cmd = list(first_config.turn_off_cmd)
        self._white_cmd = list(first_config.white_cmd)
        self._effect_speed_cmd = list(first_config.effect_speed_cmd)
        self._effect_cmd = list(first_config.effect_cmd)
        self._color_temp_cmd = list(first_config.color_temp_cmd)
        self._max_color_temp_kelvin = first_config.max_color_temp_k
        self._min_color_temp_kelvin = first_config.min_color_temp_k
        return None

    def set_rgb_gains(self, r: float, g: float, b: float) -> None:
        """Set per-channel RGB gains.

        These gains are applied when sending RGB colors (set_color), allowing
        Home Assistant color picks to better match the physical LED output.
        """
        try:
            self._rgb_gain_r = max(0.0, float(r))
            self._rgb_gain_g = max(0.0, float(g))
            self._rgb_gain_b = max(0.0, float(b))
        except (TypeError, ValueError):
            LOGGER.warning("Invalid RGB gains provided; keeping existing values")

    @staticmethod
    def _clamp_byte(value: float) -> int:
        return max(0, min(255, int(round(value))))

    def _apply_rgb_gains(self, r: int, g: int, b: int) -> tuple[int, int, int]:
        return (
            self._clamp_byte(r * self._rgb_gain_r),
            self._clamp_byte(g * self._rgb_gain_g),
            self._clamp_byte(b * self._rgb_gain_b),
        )

    @property
    def brightness_mode(self) -> str:
        """Get brightness mode: 'auto', 'rgb', or 'native'."""
        return self._brightness_mode

    @brightness_mode.setter
    def brightness_mode(self, value: str) -> None:
        """Set brightness mode."""
        if value in ("auto", "rgb", "native"):
            self._brightness_mode = value
        else:
            LOGGER.warning("Invalid brightness_mode '%s', using 'auto'", value)
            self._brightness_mode = "auto"

    def get_white_cmd(self, intensity: int):
        if self._white_cmd is None:
            return [0x7e, 0x00, 0x01, int(intensity*100/255), 0x00, 0x00, 0x00, 0x00, 0xef]
        white_cmd = self._white_cmd.copy()
        bb_index = white_cmd.index(0xbb) if 0xbb in white_cmd else -1
        if bb_index >= 0:
            white_cmd[bb_index] = int(intensity*100/255)
        return white_cmd

    def get_effect_speed_cmd(self, value: int):
        if self._effect_speed_cmd is None:
            return [0x7e, 0x00, 0x02, int(value), 0x00, 0x00, 0x00, 0x00, 0xef]
        effect_speed_cmd = self._effect_speed_cmd.copy()
        bb_index = effect_speed_cmd.index(0xbb) if 0xbb in effect_speed_cmd else -1
        if bb_index >= 0:
            effect_speed_cmd[bb_index] = int(value)
        return effect_speed_cmd

    def get_effect_cmd(self, value: int):
        if self._effect_cmd is None:
            return [0x7e, 0x00, 0x03, int(value), 0x03, 0x00, 0x00, 0x00, 0xef]
        effect_cmd = self._effect_cmd.copy()
        bb_index = effect_cmd.index(0xbb) if 0xbb in effect_cmd else -1
        if bb_index >= 0:
            effect_cmd[bb_index] = int(value)
        return effect_cmd

    def get_color_temp_cmd(self, warm: int, cold: int):
        if self._color_temp_cmd is None:
            return [0x7e, 0x00, 0x04, int(warm), int(cold), 0x00, 0x00, 0x00, 0xef]
        color_temp_cmd = self._color_temp_cmd.copy()
        # Find all 0xbb positions
        bb_indices = [i for i, v in enumerate(color_temp_cmd) if v == 0xbb]
        if len(bb_indices) >= 2:
            color_temp_cmd[bb_indices[0]] = int(warm)
            color_temp_cmd[bb_indices[1]] = int(cold)
        return color_temp_cmd

    async def _write(self, data: list[int] | bytearray):
        """Send command to device and read response."""
        await self._ensure_connected()
        await self._write_while_connected(data)

    async def _write_while_connected(self, data: list[int] | bytearray):
        LOGGER.debug(''.join(format(x, ' 03x') for x in data))
        if self._client is None:
            raise RuntimeError("BLE client not connected")
        write_data = bytearray(data) if isinstance(data, list) else data
        await self._client.write_gatt_char(self._write_uuid, write_data, False)

    @property
    def address(self):
        return self._address

    @property
    def reset(self):
        return self._reset

    @property
    def name(self):
        return self._device.name if self._device else "Unknown"

    @property
    def rssi(self):
        return 0 if self._device_data is None else self._device_data.rssi

    @property
    def is_on(self):
        return self._is_on

    @property
    def rgb_color(self):
        return self._rgb_color

    @property
    def brightness(self):
        return self._brightness

    @property
    def min_color_temp_kelvin(self):
        return self._min_color_temp_kelvin

    @property
    def max_color_temp_kelvin(self):
        return self._max_color_temp_kelvin

    @property
    def color_temp_kelvin(self):
        return self._color_temp_kelvin


    @property
    def effect(self):
        return self._effect

    @property
    def effect_speed(self):
        return self._effect_speed

    @property
    def mic_effect(self):
        return self._mic_effect

    @property
    def mic_sensitivity(self):
        return self._mic_sensitivity

    @property
    def mic_enabled(self):
        return self._mic_enabled

    @retry_bluetooth_connection_error
    async def set_color_temp(self, value: int):
        if value > 100:
            value = 100
        warm = value
        cold = 100 - value
        color_temp_cmd = self.get_color_temp_cmd(warm, cold)
        await self._write(color_temp_cmd)
        self._color_temp = warm

    @retry_bluetooth_connection_error
    async def set_color_temp_kelvin(self, value: int, brightness: int):
        """Set color temperature in Kelvin.

        For devices with native CCT support (dual white LEDs), uses native command.
        For RGB-only devices, emulates color temperature using RGB values.
        """
        self._color_temp_kelvin = value
        min_temp = self._min_color_temp_kelvin if self._min_color_temp_kelvin is not None else 1800
        max_temp = self._max_color_temp_kelvin if self._max_color_temp_kelvin is not None else 7000
        if value < min_temp:
            value = min_temp
        if value > max_temp:
            value = max_temp

        # Ensure brightness is not None before using it
        if brightness is None:
            brightness = self._brightness if self._brightness is not None else 255
        self._brightness = brightness

        # Try native CCT command first if device has color temp command
        if self._color_temp_cmd is not None:
            try:
                color_temp_percent = int(((value - min_temp) * 100) /
                                        (max_temp - min_temp)) if max_temp > min_temp else 50
                brightness_percent = int(brightness * 100 / 255)
                color_temp_cmd = self.get_color_temp_cmd(color_temp_percent, brightness_percent)
                await self._write(color_temp_cmd)
                LOGGER.debug("Used native CCT command for %dK", value)
                return
            except Exception as e:
                LOGGER.debug("Native CCT command failed, falling back to RGB emulation: %s", e)

        # RGB emulation fallback (for RGB-only devices)
        # Interpolate between warm white (2700K) and cool white (6500K) using RGB
        # Warm: amber-orange tint, Cool: slight blue tint
        # Values based on common RGB LED color temperature emulation
        warm_rgb = (255, 138, 18)   # ~1800K - very warm/orange
        cool_rgb = (180, 220, 255)  # ~7000K - cool/blue-white

        # Normalize to 0-1 range
        k_min = min_temp
        k_max = max_temp
        t = (value - k_min) / (k_max - k_min) if k_max > k_min else 1.0

        # Linear interpolation
        r = int(warm_rgb[0] + (cool_rgb[0] - warm_rgb[0]) * t)
        g = int(warm_rgb[1] + (cool_rgb[1] - warm_rgb[1]) * t)
        b = int(warm_rgb[2] + (cool_rgb[2] - warm_rgb[2]) * t)

        # Apply brightness scaling
        scale = brightness / 255.0
        r = int(r * scale)
        g = int(g * scale)
        b = int(b * scale)

        LOGGER.debug("RGB emulation for %dK: RGB(%d, %d, %d) at brightness %d", value, r, g, b, brightness)
        await self.set_color((r, g, b))

    @retry_bluetooth_connection_error
    async def set_color(self, rgb: tuple[int, int, int]):
        r, g, b = rgb
        rr, gg, bb = self._apply_rgb_gains(int(r), int(g), int(b))
        await self._write([0x7e, 0x00, 0x05, 0x03, rr, gg, bb, 0x00, 0xef])
        self._rgb_color = rgb

    @retry_bluetooth_connection_error
    async def set_white(self, intensity: int):
        if intensity is None:
            intensity = 255  # Valor por defecto si no se especifica
        white_cmd = self.get_white_cmd(intensity)
        await self._write(white_cmd)
        self._brightness = intensity

    @retry_bluetooth_connection_error
    async def set_brightness(self, intensity: int):
        await self._write([0x7e, 0x04, 0x01, int(intensity*100/255), 0xff, 0x00, 0xff, 0x00, 0xef])
        self._brightness = intensity

    @retry_bluetooth_connection_error
    async def set_effect_speed(self, value: int):
        effect_speed = self.get_effect_speed_cmd(value)
        await self._write(effect_speed)
        self._effect_speed = value

    @retry_bluetooth_connection_error
    async def set_effect(self, value: int):
        effect = self.get_effect_cmd(value)
        await self._write(effect)
        self._effect = value

    @retry_bluetooth_connection_error
    async def set_mic_effect(self, value: int):
        """Set microphone effect (0x80-0x87)."""
        if not 0x80 <= value <= 0x87:
            LOGGER.warning("Invalid mic effect value: 0x%02x, must be between 0x80 and 0x87", value)
            return
        await self._write([0x7e, 0x05, 0x03, value, 0x04, 0xff, 0xff, 0x00, 0xef])
        self._mic_effect = value
        LOGGER.debug("Mic effect set to: 0x%02x", value)

    @retry_bluetooth_connection_error
    async def set_mic_sensitivity(self, value: int):
        """Set microphone sensitivity (0-100)."""
        if not 0 <= value <= 100:
            LOGGER.warning("Invalid mic sensitivity value: %d, must be between 0 and 100", value)
            return
        await self._write([0x7e, 0x04, 0x06, value, 0xff, 0xff, 0xff, 0x00, 0xef])
        self._mic_sensitivity = value
        LOGGER.debug("Mic sensitivity set to: %d", value)

    @retry_bluetooth_connection_error
    async def enable_mic(self):
        """Enable external microphone."""
        await self._write([0x7e, 0x04, 0x07, 0x01, 0xff, 0xff, 0xff, 0x00, 0xef])
        self._mic_enabled = True
        LOGGER.debug("External microphone enabled")

    @retry_bluetooth_connection_error
    async def disable_mic(self):
        """Disable external microphone."""
        await self._write([0x7e, 0x04, 0x07, 0x00, 0xff, 0xff, 0xff, 0x00, 0xef])
        self._mic_enabled = False
        LOGGER.debug("External microphone disabled")

    @retry_bluetooth_connection_error
    async def turn_on(self):
        if self._turn_on_cmd is None:
            LOGGER.error("%s: Turn on command not configured", self.name)
            return
        # ELK-BLEDDM: detect which variant works on first call
        if self._model == "ELK-BLEDDM" and not self._bleddm_variant_checked:
            self._bleddm_variant_checked = True
            self._notification_received = False
            await self._write(self._turn_on_cmd)
            await asyncio.sleep(0.3)
            if not self._notification_received:
                LOGGER.debug("%s: Primary cmd no response, trying alternate", self.name)
                bleddm_config = MODEL_DB["ELK-BLEDDM"]
                if bleddm_config.alt_turn_on_cmd is not None:
                    self._turn_on_cmd = list(bleddm_config.alt_turn_on_cmd)
                if bleddm_config.alt_turn_off_cmd is not None:
                    self._turn_off_cmd = list(bleddm_config.alt_turn_off_cmd)
                await self._write(self._turn_on_cmd)
        else:
            await self._write(self._turn_on_cmd)
        self._is_on = True

    @retry_bluetooth_connection_error
    async def turn_off(self):
        if self._turn_off_cmd is None:
            LOGGER.error("%s: Turn off command not configured", self.name)
            return
        await self._write(self._turn_off_cmd)
        self._is_on = False

    @retry_bluetooth_connection_error
    async def set_scheduler_on(self, days: int, hours: int, minutes: int, enabled: bool):
        if enabled:
            value = days + 0x80
        else:
            value = days
        await self._write([0x7e, 0x00, 0x82, hours, minutes, 0x00, 0x00, value, 0xef])

    @retry_bluetooth_connection_error
    async def set_scheduler_off(self, days: int, hours: int, minutes: int, enabled: bool):
        if enabled:
            value = days + 0x80
        else:
            value = days
        await self._write([0x7e, 0x00, 0x82, hours, minutes, 0x00, 0x01, value, 0xef])

    @retry_bluetooth_connection_error
    async def sync_time(self):
        now = datetime.now()
        day_of_week = now.isoweekday()
        await self._write([0x7e, 0x00, 0x83, int(now.strftime('%H')), int(now.strftime('%M')), int(now.strftime('%S')), day_of_week, 0x00, 0xef])

    @retry_bluetooth_connection_error
    async def custom_time(self, hour: int, minute: int, second: int, day_of_week: int):
        await self._write([0x7e, 0x00, 0x83, hour, minute, second, day_of_week, 0x00, 0xef])

    def _get_query_cache_file(self) -> Path:
        """Get path to query command cache file."""
        # Store in Home Assistant config directory
        config_dir = Path(self._hass.config.path())
        cache_dir = config_dir / "custom_components" / "elkbledom" / ".cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir / "query_commands.json"

    def _load_working_query_cmd(self) -> bool:
        """Load previously detected working query command."""
        try:
            cache_file = self._get_query_cache_file()
            if cache_file.exists():
                with open(cache_file) as f:
                    cache = json.load(f)
                    device_key = f"{self.name}_{self._model}"
                    if device_key in cache:
                        self._working_query_cmd = cache[device_key]["command"]
                        cmd_desc = cache[device_key]["description"]
                        LOGGER.info("%s: Loaded cached query command: %s", self.name, cmd_desc)
                        return True
        except Exception as e:
            LOGGER.debug("%s: Could not load query cache: %s", self.name, e)
        return False

    def _save_working_query_cmd(self, cmd: list, description: str) -> None:
        """Save working query command to cache."""
        try:
            cache_file = self._get_query_cache_file()
            cache = {}
            if cache_file.exists():
                with open(cache_file) as f:
                    cache = json.load(f)

            device_key = f"{self.name}_{self._model}"
            cache[device_key] = {
                "command": cmd,
                "description": description,
                "device_name": self.name,
                "model": self._model
            }

            with open(cache_file, 'w') as f:
                json.dump(cache, f, indent=2)

            LOGGER.info("%s: Saved working query command: %s", self.name, description)
        except Exception as e:
            LOGGER.warning("%s: Could not save query cache: %s", self.name, e)

    async def query_state(self):
        """Query device state by testing multiple commands and saving the one that works."""
        if not self._client or not self._client.is_connected:
            return

        # If we already know the working command, use it
        if self._working_query_cmd:
            try:
                LOGGER.debug("%s: Using known working query command", self.name)
                await self._write_while_connected(self._working_query_cmd)
                await asyncio.sleep(0.2)
                return
            except Exception as e:
                LOGGER.debug("%s: Error with saved query: %s", self.name, e)
                return

        # Detection already attempted
        if self._query_detection_done:
            return

        # Try to load from cache first
        if self._load_working_query_cmd():
            self._query_detection_done = True
            # Test it
            try:
                if self._working_query_cmd is not None:
                    await self._write_while_connected(self._working_query_cmd)
                    await asyncio.sleep(0.2)
            except Exception as e:
                LOGGER.debug("%s: Cached command failed: %s", self.name, e)
            return

        # Auto-detection: try each command and see which gets a response
        LOGGER.info("%s: Auto-detecting working query command (testing %d commands)...",
                    self.name, len(QUERY_COMMANDS))

        for cmd, description in QUERY_COMMANDS:
            try:
                self._notification_received = False
                LOGGER.debug("%s: Testing: %s -> %s", self.name, description,
                           ' '.join(f'{x:02x}' for x in cmd))

                await self._write_while_connected(cmd)
                await asyncio.sleep(0.4)  # Wait for response

                if self._notification_received:
                    LOGGER.info("%s: ✓ Found working command: %s", self.name, description)
                    self._working_query_cmd = cmd
                    self._save_working_query_cmd(cmd, description)
                    self._query_detection_done = True
                    return

            except Exception as e:
                LOGGER.debug("%s: Command failed: %s - %s", self.name, description, e)
                continue

        LOGGER.info("%s: No query command found (device may not support state queries)", self.name)
        self._query_detection_done = True

    @retry_bluetooth_connection_error
    async def update(self):
        try:
            await self._ensure_connected()

            # Initialize state if not yet known (device doesn't report state)
            if self._is_on is None:
                self._is_on = False
                self._rgb_color = (0, 0, 0)
                self._color_temp_kelvin = 5000
                self._brightness = 255

            if self._device_data is not None:
                self._device_data.update_device()

        except Exception as error:
            self._is_on = False
            LOGGER.error("Error getting status: %s", error)
            track = traceback.format_exc()
            LOGGER.debug(track)

    async def _ensure_connected(self) -> None:
        """Ensure connection to device is established."""
        if self._connect_lock.locked():
            LOGGER.debug(
                "%s: Connection already in progress, waiting for it to complete; RSSI: %s",
                self.name,
                self.rssi,
            )
        if self._client and self._client.is_connected:
            self._reset_disconnect_timer()
            return
        async with self._connect_lock:
            # Check again while holding the lock
            if self._client and self._client.is_connected:
                self._reset_disconnect_timer()
                return

            LOGGER.debug("%s: Connecting; RSSI: %s", self.name, self.rssi)
            try:
                client = await establish_connection(
                        BleakClientWithServiceCache,
                        self._device,
                        self.name,
                        self._disconnected,
                        cached_services=self._cached_services,
                        ble_device_callback=lambda: self._device,
                    )
            except TimeoutError:
                LOGGER.error("%s: Connection attempt timed out; RSSI: %s", self.name, self.rssi)
                return

            LOGGER.debug("%s: Connected; RSSI: %s", self.name, self.rssi)

            resolved = self._resolve_characteristics(client.services)
            if not resolved:
                # Try to handle services failing to load
                try:
                    resolved = self._resolve_characteristics(await client.get_services())
                    self._cached_services = client.get_services() if resolved else None
                except (AttributeError):
                    LOGGER.warning("%s: Could not resolve characteristics from services; RSSI: %s", self.name, self.rssi)
            else:
                self._cached_services = client.services if resolved else None

            if not resolved:
                await client.clear_cache()
                await client.disconnect()
                raise CharacteristicMissingError(
                    "Failed to find supported characteristics, device may not be supported"
                )

            LOGGER.debug("%s: Characteristics resolved: %s; RSSI: %s", self.name, resolved, self.rssi)

            self._client = client
            self._reset_disconnect_timer()

            await self._login_command()

            # Enable notifications (simple method, no manual CCCD)
            try:
                device_name_lower = self._device.name.lower() if self._device and self._device.name else ""
                if not device_name_lower.startswith("melk") and not device_name_lower.startswith("ledble"):
                    if self._read_uuid is not None and self._read_uuid != "None":
                        LOGGER.debug("%s: Enabling notifications; RSSI: %s", self.name, self.rssi)
                        await client.start_notify(self._read_uuid, self._notification_handler)
                        LOGGER.info("%s: Notifications enabled", self.name)
                    else:
                        LOGGER.warning("%s: Read UUID not resolved (value: %s), skipping notifications", self.name, self._read_uuid)
            except Exception as e:
                LOGGER.warning("%s: Notifications could not be enabled: %s", self.name, e)

    async def _login_command(self):
        try:
            device_name_lower = self._device.name.lower() if self._device and self._device.name else ""
            if device_name_lower.startswith("modelx"):
                LOGGER.debug("Executing login command for: %s; RSSI: %s", self.name, self.rssi)
                await self._write([0x7e, 0x07, 0x83])
                await asyncio.sleep(1)
                await self._write([0x7e, 0x04, 0x04])
                await asyncio.sleep(1)
            else:
                LOGGER.debug("login command for: %s not needed; RSSI: %s", self.name, self.rssi)

        except Exception as error:
            LOGGER.error("Error login command: %s", error)
            track = traceback.format_exc()
            LOGGER.debug(track)

    async def _init_command(self):
        try:
            device_name_lower = self._device.name.lower() if self._device and self._device.name else ""
            if device_name_lower.startswith("melk"):
                LOGGER.debug("Executing init command for: %s; RSSI: %s", self.name, self.rssi)
                await self._write([0x7e, 0x07, 0x83])
                await asyncio.sleep(1)
                await self._write([0x7e, 0x04, 0x04])
                await asyncio.sleep(1)
            else:
                LOGGER.debug("init command for: %s not needed; RSSI: %s", self.name, self.rssi)

        except Exception as error:
            LOGGER.error("Error login command: %s", error)
            track = traceback.format_exc()
            LOGGER.debug(track)

    def _notification_handler(self, _sender: BleakGATTCharacteristic, data: bytearray) -> None:
        """Handle notification responses."""
        self._notification_received = True  # Mark that we got a response
        LOGGER.info("%s: ✓ Notification received (%d bytes): %s", self.name, len(data), ' '.join(f'{x:02x}' for x in data))

        # Parse notification data if available
        if len(data) >= 9 and data[0] == 0x7e and data[8] == 0xef:
            # Valid response packet
            cmd_type = data[2]

            # Status response (0x01)
            if cmd_type == 0x01:
                # Power state might be in data[3]
                power_state = data[3]
                if power_state in [0x23, 0xf0, 0x01]:
                    self._is_on = True
                    LOGGER.debug("%s: Parsed power state: ON", self.name)
                elif power_state in [0x24, 0x00]:
                    self._is_on = False
                    LOGGER.debug("%s: Parsed power state: OFF", self.name)

                # Try to parse RGB color if available
                if len(data) >= 8:
                    r, g, b = data[4], data[5], data[6]
                    if r != 0xff or g != 0xff or b != 0xff:  # Not default/invalid values
                        self._rgb_color = (r, g, b)
                        LOGGER.debug("%s: Parsed RGB color: (%d, %d, %d)", self.name, r, g, b)

                # Brightness might be in data[7]
                if len(data) >= 8 and data[7] != 0xff:
                    brightness_percent = data[7]
                    self._brightness = int(brightness_percent * 255 / 100)
                    LOGGER.debug("%s: Parsed brightness: %d%%", self.name, brightness_percent)

        return

    def _resolve_characteristics(self, services: BleakGATTServiceCollection) -> bool:
        """Resolve characteristics."""
        if not services:
            LOGGER.debug("%s: No services provided to resolve characteristics, dont should works", self.name)

        # Log all available characteristics for debugging
        LOGGER.debug("%s: Available services and characteristics:", self.name)
        for service in services:
            LOGGER.debug("%s: Service %s", self.name, service.uuid)
            for char in service.characteristics:
                LOGGER.debug("%s:   Characteristic %s (properties: %s)", self.name, char.uuid, char.properties)

        # Get unique UUIDs from MODEL_DB
        read_uuids, write_uuids = get_all_characteristic_uuids()

        # Try to find read characteristic
        for characteristic in read_uuids:
            if char := services.get_characteristic(characteristic):
                self._read_uuid = char.uuid
                LOGGER.debug("%s: Found read UUID: %s with handle %s", self.name, self._read_uuid, char.handle if hasattr(char, 'handle') else 'Unknown')
                break

        if not self._read_uuid:
            LOGGER.warning("%s: Could not find any read characteristic from: %s", self.name, read_uuids)

        # Try to find write characteristic
        for characteristic in write_uuids:
            if char := services.get_characteristic(characteristic):
                self._write_uuid = char.uuid
                LOGGER.debug("%s: Found write UUID: %s with handle %s", self.name, self._write_uuid, char.handle if hasattr(char, 'handle') else 'Unknown')
                if self.name == "ELK-BLEDOM" and char.handle if hasattr(char, 'handle') else 'Unknown' == 0x000d:
                    LOGGER.debug("%s: Adjusting model for ELK-BLEDOM specific handle issue", self.name)
                    # Use ELK-BLEDDM config for this edge case
                    config = MODEL_DB["ELK-BLEDDM"]
                    self._turn_on_cmd = list(config.turn_on_cmd)
                    self._turn_off_cmd = list(config.turn_off_cmd)
                    self._white_cmd = list(config.white_cmd)
                    self._effect_speed_cmd = list(config.effect_speed_cmd)
                    self._effect_cmd = list(config.effect_cmd)
                    self._color_temp_cmd = list(config.color_temp_cmd)
                    self._max_color_temp_kelvin = config.max_color_temp_k
                    self._min_color_temp_kelvin = config.min_color_temp_k
                break

        if not self._write_uuid:
            LOGGER.error("%s: Could not find any write characteristic from: %s", self.name, write_uuids)

        return bool(self._read_uuid and self._write_uuid)

    def _reset_disconnect_timer(self) -> None:
        """Reset disconnect timer."""
        if self._disconnect_timer:
            self._disconnect_timer.cancel()
        self._expected_disconnect = False
        if self._delay is not None and self._delay != 0:
            LOGGER.debug("%s: Configured disconnect from device in %s seconds; RSSI: %s", self.name, self._delay, self.rssi)
            self._disconnect_timer = self.loop.call_later(
                self._delay, self._disconnect
            )

    def _disconnected(self, client: BleakClientWithServiceCache) -> None:
        """Disconnected callback."""
        if self._expected_disconnect:
            LOGGER.debug("%s: Disconnected from device; RSSI: %s", self.name, self.rssi)
            return
        LOGGER.warning("%s: Device unexpectedly disconnected; RSSI: %s",self.name,self.rssi,)

    def _disconnect(self) -> None:
        """Disconnect from device."""
        self._disconnect_timer = None
        asyncio.create_task(self._execute_timed_disconnect())

    async def stop(self) -> None:
        """Stop the LEDBLE."""
        LOGGER.debug("%s: Stop", self.name)
        await self._execute_disconnect()

    async def _execute_timed_disconnect(self) -> None:
        """Execute timed disconnection."""
        LOGGER.debug(
            "%s: Disconnecting after timeout of %s",
            self.name,
            self._delay,
        )
        await self._execute_disconnect()
    async def _execute_disconnect(self) -> None:
        """Execute disconnection."""
        async with self._connect_lock:
            read_char = self._read_uuid
            client = self._client
            LOGGER.debug("Disconnecting: READ_UUID=%s, CLIENT_CONNECTED=%s", read_char, client.is_connected if client else "No Client")
            self._expected_disconnect = True
            self._client = None
            self._write_uuid = None
            self._read_uuid = None
            if client and client.is_connected:
                try:
                    device_name_lower = self._device.name.lower() if self._device and self._device.name else ""
                    if not device_name_lower.startswith("melk") and not device_name_lower.startswith("ledble"):
                        await client.stop_notify(read_char)
                    await client.disconnect()
                except Exception as e:
                    LOGGER.error("Error during disconnection: %s", e)
