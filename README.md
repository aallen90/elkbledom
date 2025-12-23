# elkbledom HA Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Home Assistant integration for LED STRIP or LED Desktop light (lightbar) NAME ELK BLEDOM with android/iphone mobile app duoCo Strip (https://play.google.com/store/apps/details?id=shy.smartled&hl=es&gl=US) or mobile app Lantern Lotus (https://play.google.com/store/apps/details?id=wl.smartled&hl=es&gl=US) or mobile app Lotus Lamp X (https://play.google.com/store/apps/details?id=com.szelk.ledlamppro).

> **Note:** This is a fork of [dave-code-ruiz/elkbledom](https://github.com/dave-code-ruiz/elkbledom) with additional features and improvements. Some features (emoji effect labels, color temperature emulation) were inspired by [Satimaro/elkbledom-fastlink](https://github.com/Satimaro/elkbledom-fastlink).

## Supported Devices

| Device Name | Status | Notes |
|-------------|--------|-------|
| ELK-BLE* | ✅ Supported | Original LED strips |
| ELK-BLEDOM | ✅ Supported | Standard variant (0x04 command byte) |
| **ELK-BLEDDM** | ✅ Supported | Alternate variant (0x00 command byte) - auto-detected |
| ELK-BULB* | ✅ Supported | LED bulbs |
| ELK-LAMPL* | ✅ Supported | Works with Lotus Lamp X app |
| MELK* | ✅ Supported | Requires init commands (see below) |
| LEDBLE* | ✅ Supported | Generic LED strips |

## Fork Enhancements (v1.6.0+)

This fork adds several improvements over the original:

- **ELK-BLEDDM variant support** - Automatic detection of 0x00 vs 0x04 command byte variants
- **RGB color calibration** - Configurable per-channel gains (r/g/b) for white balance
- **Sync Time button** - Synchronize device time with Home Assistant
- **RSSI sensor** - Monitor Bluetooth signal strength (disabled by default)
- **Emoji effect labels** - Visual effect names (🌈 Smooth Cycle, ⚡ Jump RGB, etc.)
- **Brightness mode option** - Choose between auto, RGB, or native brightness control
- **Color temperature emulation** - RGB-based color temp (1800K-7000K) for devices without native CCT
- **CoordinatorEntity pattern** - Modern HA architecture with centralized polling
- **HA best practices** - Proper entity naming, categories, and icon translations

## Dependencies

`gattool` is used to query the BLE device.
It is available in `bluez-deprecated` for Fedora:

```
sudo dnf install bluez-deprecated
```

or as `bluez-deprecated-tools` in Arch:

```
paru -S bluez-deprecated-tools
```

BTScan.py relies on bluepy, and the integration relies on bleak-retry-connector and bleak pip packages.

```
pip install -r requirements.txt
```

## Supported UUIDs

You can scan BT device with BTScan.py in my repository exec: `sudo python3 BTScan.py`, code supports led strips whose name begins with "ELK-BLE" or "ELK-BLEDDM" or "MELK" or "ELK-BULB" or "LEDBLE".

Code supports controlling lights in HA with write uuid: 0000fff3-0000-1000-8000-00805f9b34fb or 0000ffe1-0000-1000-8000-00805f9b34fb

You can know your uuid with gatttool:

```

gatttool -I

[be:59:7a:00:08:xx][LE]> connect be:59:7a:00:08:xx

Attempting to connect to be:59:7a:00:08:xx

Connection successful

[be:59:7a:00:08:xx][LE]> primary
attr handle: 0x0001, end grp handle: 0x0003 uuid: 00001800-0000-1000-8000-00805f9b34fb
attr handle: 0x0004, end grp handle: 0x0009 uuid: 0000fff0-0000-1000-8000-00805f9b34fb

[be:59:7a:00:08:xx][LE]> Characteristics
handle: 0x0002, char properties: 0x12, char value handle: 0x0003, uuid: 00002a00-0000-1000-8000-00805f9b34fb
handle: 0x0005, char properties: 0x10, char value handle: 0x0006, uuid: 0000fff4-0000-1000-8000-00805f9b34fb
handle: 0x0008, char properties: 0x06, char value handle: 0x0009, uuid: 0000fff3-0000-1000-8000-00805f9b34fb

```

If your strip show some uuid like "**0000fff3**-0000-1000-8000-00805f9b34fb" , your strip it is supported

If your strip show some uuid like "**0000ffe1**-0000-1000-8000-00805f9b34fb" , your strip it is supported

If your strip show some uuid like "**0000ff01**-0000-1000-8000-00805f9b34fb", go to your correct repository: https://github.com/raulgbcr/lednetwf_ble

If your strip show some uuid like:

    "0000xxxx-0000-1000-8000-00805f9b34fb"
    xxxx can be one of these values ("ff01", "ffd5", "ffd9", "ffe5", "ffe9", "ff02", "ffd0", "ffd4", "ffe0", "ffe4")

Go to your correct repository: https://www.home-assistant.io/integrations/led_ble/

If your uuid is none of the above, create issue with: 1- strip name 2- your results uuid 3- handle information

You can use gatttool to try discover your turn on/off command with:

```
sudo gatttool -i hci0 -b be:59:7a:00:08:xx --char-write-req -a 0x0009 -n 7e00040100000000ef # POWERON
sudo gatttool -i hci0 -b be:59:7a:00:08:xx --char-write-req -a 0x0009 -n 7e0004000000ff00ef # POWEROFF

#ANOTHER TURN ON COMMANDS
#7e0404f00001ff00ef
#7e0004f00001ff00ef
#7e00040100000000ef
#7e0704FF00010201ef

#ANOTHER TURN OFF COMMANDS
#7e0404000000ff00ef
#7e00040100000000ef
#7e0004000000ff00ef
#7e00040000000200ef

```

or

```
sudo gatttool -b be:59:7a:00:08:xx --char-write-req -a 0x0009 -n 7e000503ff000000ef # RED
sudo gatttool -b be:59:7a:00:08:xx --char-write-req -a 0x0009 -n 7e0005030000ff00ef # BLUE
sudo gatttool -b be:59:7a:00:08:xx --char-write-req -a 0x0009 -n 7e00050300ff0000ef # GREEN
```

## Installation

### [HACS](https://hacs.xyz/) (recommended)

Since this is a fork, you need to add it as a custom repository:

1. Open HACS in Home Assistant
2. Click the three dots menu → **Custom repositories**
3. Add `https://github.com/aallen90/elkbledom` with category **Integration**
4. Search for "ElkBLEDOM" and install
5. Restart Home Assistant

### Manual installation

You can manually clone this repository inside `config/custom_components/` HA folder.

## Setup

After installation, you should find elkbledom under the Settings -> Integrations -> Add integration -> search elkbledom integration -> follow instructions.

The setup step includes discovery which will list out all ELK BLEDOM lights discovered. The setup will validate connection by toggling the selected light. Make sure your light is in-sight to validate this.

The setup needs to be repeated for each light.

## Init command in MELK strips

If your strip model is MELK , i have an issue open about your problem, #11 and you need to send to the strip two init commands , i dont know why , something weird, but work fine:

`
sudo gatttool -b BE:16:F8:1D:D6:66 --char-write-req -a 0x0009 -n 7e0783
`
`
sudo gatttool -b BE:16:F8:1D:D6:66 --char-write-req -a 0x0009 -n 7e0404
`

after that, try to restart strip, add your strip to homeassistant and i think you could work with your strip normally

## Config

After Setup, you can configure elkbledom params under Settings → Integrations → ElkBLEDOM → Configure.

#### Reset color when LED turns on

When LED strip turns on, reset to color white. Useful if external controls (IR remote) changed the state.

#### Disconnect delay or timeout

Time before disconnecting from the LED strip (0 = never disconnect).

#### RGB Gain (R/G/B)

Color calibration for white balance. Values 0.0-3.0. Use `test_device.py` to find optimal values for your device.

#### Brightness Mode

- **auto** - Integration chooses the best method
- **rgb** - Scale RGB values for brightness (better color accuracy)
- **native** - Use device's brightness command

## Features

#### Discovery

Automatically discover ELK BLEDOM based lights without manually hunting for Bluetooth MAC address.

#### On/Off/RGB/Brightness support

#### Color Temperature Emulation

RGB-based color temperature from 1800K (warm) to 7000K (cool) for devices without native CCT.

#### Effect Support

Light effects with emoji labels: 🌈 Smooth Cycle, ⚡ Jump RGB, 💓 Breathing, and more.

#### Multiple light support

#### Microphone Effects

Sound-reactive effects with sensitivity control (on supported devices).

## Not supported

#### Live state polling

External control (i.e. IR remote) state changes do NOT reflect in Home Assistant and are NOT updated.

## Hardware Limitations

These are inherent limitations of the ELK-BLEDOM hardware that cannot be fixed in software:

1. **Single Bluetooth connection** - Only one device can be connected to the LED strip at a time. If you're using the mobile app or `gatttool`, disconnect first.
   ```
   BleakOutOfConnectionSlotsError: Failed to connect after 9 attempt(s)
   ```

2. **IR interference** - Some LED strips may respond to TV remotes or other IR devices, causing unexpected state changes.

3. **No state feedback** - The device doesn't report its current state, so Home Assistant assumes state based on commands sent.

## TODO / Future Improvements

- [ ] **Investigate state read command** - The device may support a status query command (e.g., `0xEF 0x01 0x77`). If found, this would enable state sync after reconnect.
- [x] **Refactor model database** - Clean up device variant handling with a proper ModelDB structure instead of arrays. ✅ Completed - now uses `ModelConfig` dataclass with `MODEL_DB` dictionary.
- [ ] **Add `assumed_state` property** - Indicate to HA that state may be uncertain, showing toggle UI instead of on/off.

## Enable debug mode

Use debug log to see more information of posible errors and post it in your issue description

In configuration.yaml:

```
logger:
  default: info
  logs:
    custom_components.elkbledom: debug
```

## Examples

Create button to turn on:

```
show_name: true
show_icon: true
name: turn on
type: button
tap_action:
  action: toggle
entity: light.tiraled
```

Create button to set color:

```
show_name: true
show_icon: true
name: Red
type: button
tap_action:
  action: call-service
  service: light.turn_on
  target:
    entity_id: light.test
  data:
    rgb_color:
      - 255
      - 0
      - 0
    brightness: 255
```

## Credits

This integration would not be possible without the awesome work of these repositories:

- [Home Assistant LED BLE](https://www.home-assistant.io/integrations/led_ble/)
- [sysofwan/ha-triones](https://github.com/sysofwan/ha-triones)
- [TheSylex/ELK-BLEDOM-bluetooth-led-strip-controller](https://github.com/TheSylex/ELK-BLEDOM-bluetooth-led-strip-controller/)
- [FreekBes/bledom_controller](https://github.com/FreekBes/bledom_controller/)
- [FergusInLondon/ELK-BLEDOM](https://github.com/FergusInLondon/ELK-BLEDOM/)
- [arduino12/ble_rgb_led_strip_controller](https://github.com/arduino12/ble_rgb_led_strip_controller)
- [lilgallon/DynamicLedStrips](https://github.com/lilgallon/DynamicLedStrips)
- [kquinsland/JACKYLED-BLE-RGB-LED-Strip-controller](https://github.com/kquinsland/JACKYLED-BLE-RGB-LED-Strip-controller)

https://linuxthings.co.uk/blog/control-an-elk-bledom-bluetooth-led-strip
