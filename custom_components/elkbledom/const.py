from enum import Enum

DOMAIN = "elkbledom"
CONF_RESET = "reset"
CONF_DELAY = "delay"

# Per-device RGB calibration gains applied to RGB writes.
CONF_RGB_GAIN_R = "rgb_gain_r"
CONF_RGB_GAIN_G = "rgb_gain_g"
CONF_RGB_GAIN_B = "rgb_gain_b"

# Brightness mode: auto, rgb, or native
# Some devices respond better to different brightness commands
CONF_BRIGHTNESS_MODE = "brightness_mode"
BRIGHTNESS_MODES = ["auto", "rgb", "native"]
DEFAULT_BRIGHTNESS_MODE = "auto"


class ConnectionState(Enum):
    """Connection state machine for BLE device."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    READY = "ready"  # Connected and notifications enabled
    ERROR = "error"


class EFFECTS (Enum):
    # Light Effects (0x87-0x9C)
    jump_red_green_blue = 0x87
    jump_red_green_blue_yellow_cyan_magenta_white = 0x88
    crossfade_red = 0x8b
    crossfade_green = 0x8c
    crossfade_blue = 0x8d
    crossfade_yellow = 0x8e
    crossfade_cyan = 0x8f
    crossfade_magenta = 0x90
    crossfade_white = 0x91
    crossfade_red_green = 0x92
    crossfade_red_blue = 0x93
    crossfade_green_blue = 0x94
    crossfade_red_green_blue = 0x89
    crossfade_red_green_blue_yellow_cyan_magenta_white = 0x8a
    blink_red = 0x96
    blink_green = 0x97
    blink_blue = 0x98
    blink_yellow = 0x99
    blink_cyan = 0x9a
    blink_magenta = 0x9b
    blink_white = 0x9c
    blink_red_green_blue_yellow_cyan_magenta_white = 0x95


# Emoji labels for effects (UI display)
# Inspired by Satimaro/elkbledom-fastlink (MIT License)
EFFECT_LABELS = {
    "jump_red_green_blue": "⚡ Jump RGB",
    "jump_red_green_blue_yellow_cyan_magenta_white": "🌈 Jump All",
    "crossfade_red": "🔴 Fade Red",
    "crossfade_green": "🟢 Fade Green",
    "crossfade_blue": "🔵 Fade Blue",
    "crossfade_yellow": "🟡 Fade Yellow",
    "crossfade_cyan": "💠 Fade Cyan",
    "crossfade_magenta": "💜 Fade Magenta",
    "crossfade_white": "🤍 Fade White",
    "crossfade_red_green": "🔴🟢 Fade R-G",
    "crossfade_red_blue": "🔴🔵 Fade R-B",
    "crossfade_green_blue": "🟢🔵 Fade G-B",
    "crossfade_red_green_blue": "🌤️ Fade RGB",
    "crossfade_red_green_blue_yellow_cyan_magenta_white": "🌈 Smooth Cycle",
    "blink_red": "🔴 Blink Red",
    "blink_green": "🟢 Blink Green",
    "blink_blue": "🔵 Blink Blue",
    "blink_yellow": "🟡 Blink Yellow",
    "blink_cyan": "💠 Blink Cyan",
    "blink_magenta": "💜 Blink Magenta",
    "blink_white": "🤍 Blink White",
    "blink_red_green_blue_yellow_cyan_magenta_white": "🎇 Blink All",
}

# Emoji labels for microphone effects
MIC_EFFECT_LABELS = {
    "mic_energic": "🎵 Energetic",
    "mic_rhythm": "🥁 Rhythm",
    "mic_spectrum": "📊 Spectrum",
    "mic_rolling": "🌊 Rolling",
    "mic_classic": "🎶 Classic",
    "mic_soft": "💫 Soft",
    "mic_dynamic": "🔊 Dynamic",
    "mic_disco": "🪩 Disco",
}

class MIC_EFFECTS (Enum):
    mic_energic = 0x80
    mic_rhythm = 0x81
    mic_spectrum = 0x82
    mic_rolling = 0x83
    mic_classic = 0x84
    mic_soft = 0x85
    mic_dynamic = 0x86
    mic_disco = 0x87

EFFECTS_list = [EFFECT_LABELS.get(e, e) for e in [
    'jump_red_green_blue',
    'jump_red_green_blue_yellow_cyan_magenta_white',
    'crossfade_red',
    'crossfade_green',
    'crossfade_blue',
    'crossfade_yellow',
    'crossfade_cyan',
    'crossfade_magenta',
    'crossfade_white',
    'crossfade_red_green',
    'crossfade_red_blue',
    'crossfade_green_blue',
    'crossfade_red_green_blue',
    'crossfade_red_green_blue_yellow_cyan_magenta_white',
    'blink_red',
    'blink_green',
    'blink_blue',
    'blink_yellow',
    'blink_cyan',
    'blink_magenta',
    'blink_white',
    'blink_red_green_blue_yellow_cyan_magenta_white'
]]

# Reverse mapping: emoji label -> effect name
EFFECT_LABEL_TO_NAME = {v: k for k, v in EFFECT_LABELS.items()}

MIC_EFFECTS_list = [MIC_EFFECT_LABELS.get(e, e) for e in [
    'mic_energic',
    'mic_rhythm',
    'mic_spectrum',
    'mic_rolling',
    'mic_classic',
    'mic_soft',
    'mic_dynamic',
    'mic_disco',
]]

# Reverse mapping: mic effect label -> effect name
MIC_EFFECT_LABEL_TO_NAME = {v: k for k, v in MIC_EFFECT_LABELS.items()}

# RGB Channel Order options
# Some LED strips have different wiring (GRB instead of RGB, etc.)
# Command 0x81 sets the channel order: [0x7e, 0x06, 0x81, R_pos, G_pos, B_pos, 0xff, 0x00, 0xef]
RGB_CHANNEL_ORDERS = {
    "RGB": (1, 2, 3),
    "RBG": (1, 3, 2),
    "GRB": (2, 1, 3),
    "GBR": (2, 3, 1),
    "BRG": (3, 1, 2),
    "BGR": (3, 2, 1),
}
RGB_CHANNEL_ORDER_LIST = list(RGB_CHANNEL_ORDERS.keys())

class WEEK_DAYS (Enum):
    monday = 0x01
    tuesday = 0x02
    wednesday = 0x04
    thursday = 0x08
    friday = 0x10
    saturday = 0x20
    sunday = 0x40
    all = (0x01 + 0x02 + 0x04 + 0x08 + 0x10 + 0x20 + 0x40)
    week_days = (0x01 + 0x02 + 0x04 + 0x08 + 0x10)
    weekend_days = (0x20 + 0x40)
    none = 0x00

#print(EFFECTS.blink_red.value)
