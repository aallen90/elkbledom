#!/usr/bin/env python3
"""Interactive tool to test ELK-BLEDDM commands and calibrate colors."""

import asyncio
import colorsys
from bleak import BleakClient

DEVICE_MAC = "BE:27:EB:01:83:20"
WRITE_UUID = "0000fff3-0000-1000-8000-00805f9b34fb"
READ_UUID = "0000fff4-0000-1000-8000-00805f9b34fb"

# Simple per-channel gain calibration (applied to RGB writes only)
RGB_GAINS = {"r": 1.0, "g": 1.0, "b": 1.0}

# Some devices expect non-RGB channel ordering (common: GRB).
CHANNEL_ORDER = "rgb"  # one of: rgb, rbg, grb, gbr, brg, bgr


def _clamp_byte(value: int) -> int:
    return max(0, min(255, int(value)))


def apply_rgb_gains(r: int, g: int, b: int) -> tuple[int, int, int]:
    return (
        _clamp_byte(r * RGB_GAINS["r"]),
        _clamp_byte(g * RGB_GAINS["g"]),
        _clamp_byte(b * RGB_GAINS["b"]),
    )


def apply_channel_order(r: int, g: int, b: int) -> tuple[int, int, int]:
    mapping = {
        "rgb": (r, g, b),
        "rbg": (r, b, g),
        "grb": (g, r, b),
        "gbr": (g, b, r),
        "brg": (b, r, g),
        "bgr": (b, g, r),
    }
    return mapping.get(CHANNEL_ORDER, (r, g, b))


def hsv_to_rgb_bytes(h: float, s: float, v: float) -> tuple[int, int, int]:
    """Convert HSV (h in [0,360), s/v in [0,1]) -> RGB bytes."""
    h = (h % 360.0) / 360.0
    s = max(0.0, min(1.0, s))
    v = max(0.0, min(1.0, v))
    r_f, g_f, b_f = colorsys.hsv_to_rgb(h, s, v)
    return (int(round(r_f * 255)), int(round(g_f * 255)), int(round(b_f * 255)))


async def send_rgb(client: BleakClient, r: int, g: int, b: int, desc: str = "") -> None:
    rr, gg, bb = apply_rgb_gains(r, g, b)
    rr, gg, bb = apply_channel_order(rr, gg, bb)
    await send_cmd(
        client,
        [0x7e, 0x00, 0x05, 0x03, rr, gg, bb, 0x00, 0xef],
        desc or f"RGB({r},{g},{b}) -> ({rr},{gg},{bb}) order={CHANNEL_ORDER} gains r={RGB_GAINS['r']:.3f} g={RGB_GAINS['g']:.3f} b={RGB_GAINS['b']:.3f}",
    )


async def color_mixing_menu(client: BleakClient) -> None:
    """Interactive color mixing (HSV) + channel-order verification."""
    global CHANNEL_ORDER
    print("\n=== Color Mixing (HSV) ===")
    print(
        "Commands: hsv <h> <s> <v>, hue, order <rgb|rbg|grb|gbr|brg|bgr>, "
        "primaries, secondaries, gray <0-255>, sweep <yellow|cyan|magenta>, "
        "r+/r-/g+/g-/b+/b-, step <float>, show, done"
    )
    print("Notes: If 'red' shows up as green, try a different order (GRB is common).")

    step = 0.05
    last_rgb: tuple[int, int, int] = (255, 255, 255)

    while True:
        cmd = input("mix> ").strip().lower()
        if cmd in {"done", "exit", "quit"}:
            print(f"Using CHANNEL_ORDER={CHANNEL_ORDER}")
            return

        if cmd == "show":
            print(
                f"order={CHANNEL_ORDER} gains: r={RGB_GAINS['r']:.3f} g={RGB_GAINS['g']:.3f} b={RGB_GAINS['b']:.3f} (step={step:.3f})"
            )
            continue

        if cmd.startswith("step "):
            try:
                step = float(cmd.split(maxsplit=1)[1])
                if step <= 0:
                    raise ValueError
            except ValueError:
                print("Invalid step; expected a positive float (e.g. step 0.05)")
            continue

        if cmd.startswith("order "):
            value = cmd.split(maxsplit=1)[1]
            if value not in {"rgb", "rbg", "grb", "gbr", "brg", "bgr"}:
                print("Invalid order. Use one of: rgb rbg grb gbr brg bgr")
                continue
            CHANNEL_ORDER = value
            print(f"CHANNEL_ORDER set to {CHANNEL_ORDER}")
            continue

        if cmd == "primaries":
            print("Showing primaries. Press Enter to advance.")
            last_rgb = (255, 0, 0)
            await send_rgb(client, *last_rgb, "Primary: RED")
            input("Enter for GREEN...")
            last_rgb = (0, 255, 0)
            await send_rgb(client, *last_rgb, "Primary: GREEN")
            input("Enter for BLUE...")
            last_rgb = (0, 0, 255)
            await send_rgb(client, *last_rgb, "Primary: BLUE")
            continue

        if cmd == "secondaries":
            print("Showing secondaries. Press Enter to advance.")
            last_rgb = (255, 255, 0)
            await send_rgb(client, *last_rgb, "Secondary: YELLOW (R+G)")
            input("Enter for CYAN...")
            last_rgb = (0, 255, 255)
            await send_rgb(client, *last_rgb, "Secondary: CYAN (G+B)")
            input("Enter for MAGENTA...")
            last_rgb = (255, 0, 255)
            await send_rgb(client, *last_rgb, "Secondary: MAGENTA (R+B)")
            input("Enter for WHITE...")
            last_rgb = (255, 255, 255)
            await send_rgb(client, *last_rgb, "White (R+G+B)")
            continue

        if cmd.startswith("gray "):
            try:
                lvl = int(cmd.split(maxsplit=1)[1])
                if not 0 <= lvl <= 255:
                    raise ValueError
            except ValueError:
                print("Expected: gray <0-255> (e.g. gray 180)")
                continue
            last_rgb = (lvl, lvl, lvl)
            await send_rgb(client, *last_rgb, f"Gray {lvl}")
            continue

        if cmd.startswith("sweep "):
            mode = cmd.split(maxsplit=1)[1].strip()
            if mode not in {"yellow", "cyan", "magenta"}:
                print("Expected: sweep <yellow|cyan|magenta>")
                continue
            print("Press Enter to step; type Ctrl+C to abort sweep.")
            try:
                if mode == "yellow":
                    # Keep B=0; vary G up from warm/orange toward yellow.
                    for g in [64, 96, 128, 160, 192, 224, 255]:
                        last_rgb = (255, g, 0)
                        await send_rgb(client, *last_rgb, f"Sweep yellow: R=255 G={g} B=0")
                        input("Enter...")
                elif mode == "cyan":
                    # Keep R=0; vary G/B ratio to find the deepest cyan (least white).
                    for g, b in [
                        (255, 64),
                        (255, 96),
                        (255, 128),
                        (255, 160),
                        (255, 192),
                        (255, 224),
                        (255, 255),
                        (224, 255),
                        (192, 255),
                        (160, 255),
                        (128, 255),
                        (96, 255),
                        (64, 255),
                    ]:
                        last_rgb = (0, g, b)
                        await send_rgb(client, *last_rgb, f"Sweep cyan: R=0 G={g} B={b}")
                        input("Enter...")
                else:
                    # Keep G=0; vary R/B ratio.
                    for r, b in [
                        (255, 64),
                        (255, 96),
                        (255, 128),
                        (255, 160),
                        (255, 192),
                        (255, 224),
                        (255, 255),
                        (224, 255),
                        (192, 255),
                        (160, 255),
                        (128, 255),
                        (96, 255),
                        (64, 255),
                    ]:
                        last_rgb = (r, 0, b)
                        await send_rgb(client, *last_rgb, f"Sweep magenta: R={r} G=0 B={b}")
                        input("Enter...")
            except KeyboardInterrupt:
                print("Sweep aborted")
            continue

        if cmd in {"r+", "r-", "g+", "g-", "b+", "b-"}:
            channel = cmd[0]
            direction = 1 if cmd[1] == "+" else -1
            RGB_GAINS[channel] = max(0.0, RGB_GAINS[channel] + direction * step)
            print(f"gains now: r={RGB_GAINS['r']:.3f} g={RGB_GAINS['g']:.3f} b={RGB_GAINS['b']:.3f}")
            # Auto-preview the last color to make gain tuning fast.
            await send_rgb(client, *last_rgb, f"Preview after gain tweak (last={last_rgb})")
            continue

        if cmd.startswith("hsv "):
            parts = cmd.split()
            if len(parts) != 4:
                print("Expected: hsv <h 0-360> <s 0-1> <v 0-1> (e.g. hsv 210 0.7 0.8)")
                continue
            try:
                h = float(parts[1])
                s = float(parts[2])
                v = float(parts[3])
            except ValueError:
                print("Invalid hsv values")
                continue
            r, g, b = hsv_to_rgb_bytes(h, s, v)
            last_rgb = (r, g, b)
            await send_rgb(client, r, g, b, f"HSV({h},{s},{v})")
            continue

        if cmd == "hue":
            print("Hue wheel preview (S=1, V=1). Press Enter to step.")
            for h in range(0, 360, 30):
                r, g, b = hsv_to_rgb_bytes(h, 1.0, 1.0)
                last_rgb = (r, g, b)
                await send_rgb(client, r, g, b, f"Hue {h}")
                input("Enter for next hue...")
            continue

        print(
            "Unknown command. Try: primaries, secondaries, gray 180, order grb, hsv 210 0.7 0.8, hue, show, done"
        )

def notification_handler(sender, data):
    """Handle notifications from the device."""
    print(f"  <- Notification: {data.hex(' ')}")

async def send_cmd(client, cmd_bytes, desc=""):
    """Send a command and wait for response."""
    print(f"  -> Sending: {bytes(cmd_bytes).hex(' ')}  {desc}")
    await client.write_gatt_char(WRITE_UUID, bytes(cmd_bytes), response=False)
    await asyncio.sleep(0.3)


async def rgb_calibration_menu(client: BleakClient) -> None:
    """Interactive RGB balance calibration.

    This does not attempt to be “smart”; it just helps you dial in gains by eye.
    """
    step = 0.05
    print("\n=== RGB Balance Calibration ===")
    print("Goal: make RGB white look neutral.")
    print("Commands: r+/r-/g+/g-/b+/b-, step <float>, set <r> <g> <b>, show, test, levels, base <0-255>, done")

    # Start with a mid-grey preview; full-white can saturate one channel early.
    base = 180
    test_levels = [24, 48, 80, 120, 160, 200, 240]

    while True:
        cmd = input("cal> ").strip().lower()
        if cmd in {"done", "exit", "quit"}:
            print(f"Saved gains: r={RGB_GAINS['r']:.3f} g={RGB_GAINS['g']:.3f} b={RGB_GAINS['b']:.3f}")
            return

        if cmd == "show":
            print(
                f"gains: r={RGB_GAINS['r']:.3f} g={RGB_GAINS['g']:.3f} b={RGB_GAINS['b']:.3f} "
                f"(step={step:.3f}, base={base})"
            )
            continue

        if cmd.startswith("base "):
            try:
                base = int(cmd.split(maxsplit=1)[1])
                if not 0 <= base <= 255:
                    raise ValueError
            except ValueError:
                print("Invalid base; expected integer 0-255 (e.g. base 180)")
            continue

        if cmd.startswith("step "):
            try:
                step = float(cmd.split(maxsplit=1)[1])
                if step <= 0:
                    raise ValueError
            except ValueError:
                print("Invalid step; expected a positive float (e.g. step 0.05)")
            continue

        if cmd.startswith("set "):
            parts = cmd.split()
            if len(parts) != 4:
                print("Expected: set <r> <g> <b> (e.g. set 1.00 0.92 0.88)")
                continue
            try:
                RGB_GAINS["r"] = float(parts[1])
                RGB_GAINS["g"] = float(parts[2])
                RGB_GAINS["b"] = float(parts[3])
            except ValueError:
                print("Invalid gain(s); expected floats")
            continue

        if cmd == "test":
            r, g, b = apply_rgb_gains(base, base, base)
            await send_cmd(
                client,
                [0x7e, 0x00, 0x05, 0x03, r, g, b, 0x00, 0xef],
                f"TEST grey({base}) -> ({r},{g},{b})",
            )
            continue

        if cmd == "levels":
            print("Sweeping greys: " + ", ".join(str(x) for x in test_levels))
            for lvl in test_levels:
                r, g, b = apply_rgb_gains(lvl, lvl, lvl)
                await send_cmd(
                    client,
                    [0x7e, 0x00, 0x05, 0x03, r, g, b, 0x00, 0xef],
                    f"LEVEL grey({lvl}) -> ({r},{g},{b})",
                )
                input("Press Enter for next level...")
            continue

        if cmd in {"r+", "r-", "g+", "g-", "b+", "b-"}:
            channel = cmd[0]
            direction = 1 if cmd[1] == "+" else -1
            RGB_GAINS[channel] = max(0.0, RGB_GAINS[channel] + direction * step)
            r, g, b = apply_rgb_gains(base, base, base)
            await send_cmd(client, [0x7e, 0x00, 0x05, 0x03, r, g, b, 0x00, 0xef], f"TEST -> ({r},{g},{b})")
            continue

        print("Unknown command. Try: show, test, r+/r-, g+/g-, b+/b-, step 0.05, set 1.0 1.0 1.0, done")

async def main():
    print(f"Connecting to {DEVICE_MAC}...")
    
    async with BleakClient(DEVICE_MAC) as client:
        print(f"Connected: {client.is_connected}")
        
        # Enable notifications
        await client.start_notify(READ_UUID, notification_handler)
        print("Notifications enabled\n")
        
        while True:
            print("\n=== ELK-BLEDDM Test Menu ===")
            print("1. Turn ON")
            print("2. Turn OFF")
            print("3. Set Color (RGB)")
            print("3b. Calibrate RGB balance")
            print("3c. Color mixing (HSV + order)")
            print("4. Set Brightness")
            print("5. Set White")
            print("6. Set Effect")
            print("7. Set Effect Speed")
            print("8. Send custom hex command")
            print("9. Probe all effects (0x80-0x9F)")
            print("0. Exit")
            
            choice = input("\nChoice: ").strip()
            
            if choice == "1":
                await send_cmd(client, [0x7e, 0x00, 0x04, 0xf0, 0x00, 0x01, 0xff, 0x00, 0xef], "ON")
                
            elif choice == "2":
                await send_cmd(client, [0x7e, 0x00, 0x04, 0x00, 0x00, 0x00, 0xff, 0x00, 0xef], "OFF")
                
            elif choice == "3":
                r = int(input("Red (0-255): "))
                g = int(input("Green (0-255): "))
                b = int(input("Blue (0-255): "))
                await send_rgb(client, r, g, b)

            elif choice.lower() == "3b":
                await rgb_calibration_menu(client)

            elif choice.lower() == "3c":
                await color_mixing_menu(client)
                
            elif choice == "4":
                val = int(input("Brightness (0-100): "))
                await send_cmd(client, [0x7e, 0x04, 0x01, val, 0xff, 0x00, 0xff, 0x00, 0xef], f"Brightness {val}%")
                
            elif choice == "5":
                val = int(input("White intensity (0-100): "))
                await send_cmd(client, [0x7e, 0x00, 0x01, val, 0x00, 0x00, 0x00, 0x00, 0xef], f"White {val}%")
                
            elif choice == "6":
                print("Effects: 0x80=jump RGB, 0x81=jump RGBYCMW, 0x82=crossfade RGB...")
                val = input("Effect hex (e.g. 80): ")
                effect = int(val, 16)
                await send_cmd(client, [0x7e, 0x00, 0x03, effect, 0x03, 0x00, 0x00, 0x00, 0xef], f"Effect 0x{effect:02x}")
                
            elif choice == "7":
                val = int(input("Speed (0-255, 0=fast, 255=slow): "))
                await send_cmd(client, [0x7e, 0x00, 0x02, val, 0x00, 0x00, 0x00, 0x00, 0xef], f"Speed {val}")
                
            elif choice == "8":
                hex_str = input("Hex command (e.g. 7e0004f00001ff00ef): ")
                cmd = bytes.fromhex(hex_str.replace(" ", ""))
                await send_cmd(client, list(cmd), "Custom")
                
            elif choice == "9":
                print("Probing effects 0x80-0x9F (press Ctrl+C to stop)...")
                for effect in range(0x80, 0xA0):
                    print(f"\nEffect 0x{effect:02x}:")
                    await send_cmd(client, [0x7e, 0x00, 0x03, effect, 0x03, 0x00, 0x00, 0x00, 0xef])
                    input("Press Enter for next effect...")
                    
            elif choice == "0":
                print("Exiting...")
                break
            else:
                print("Invalid choice")

if __name__ == "__main__":
    asyncio.run(main())
