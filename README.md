# Clawdmeter-EchoEar

A desk-side Claude Code usage monitor ported to the **Espressif ESP-VoCat v1.2** — a round 1.85" AMOLED ESP32-S3 board.

Pairs with your Mac over Bluetooth, shows session and weekly Claude usage, and plays pixel-art Clawd animations that get busier as your usage climbs.

## Based on

This project is a hardware port of [**Clawdmeter**](https://github.com/HermannBjorgvin/Clawdmeter) by [@hermannbjorgvin](https://github.com/HermannBjorgvin), originally built for the Waveshare ESP32-S3-Touch-AMOLED-2.16 (480×480 square AMOLED). All core firmware architecture, BLE protocol, LVGL UI design, splash animation engine, and daemon logic come from the original project.

**Changes in this port:**
- Display: ST77916 QSPI 360×360 round (ESP-VoCat v1.2), active-HIGH reset, active-LOW power enable, color inversion
- Touch: CST816S (I2C, SDA=2/SCL=1)
- Power: BQ27220 fuel gauge (replaces AXP2101)
- IMU: BMI270 stub (SensorLib 0.2.6 doesn't yet include BMI270 driver)
- Buttons: GPIO0 (Space), GPIO6/7 (capacitive pads, replaces GPIO18)
- macOS daemon: Python + `bleak`, reads OAuth token from macOS Keychain
- UI scaled to 75% with wider margins to fit circular bezel

## Hardware

- [Espressif ESP-VoCat v1.2](https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s3/esp-vocat/user_guide_v1.2.html) — ESP32-S3, 1.85" round ST77916 QSPI display (360×360), CST816S touch, BQ27220 battery gauge, BMI270 IMU
- USB-C cable for flashing and power

## Screens

| Splash | Usage | Bluetooth |
| :----: | :---: | :-------: |
| Pixel-art Clawd animation | Session & weekly utilization | Connection status & bond reset |

The device boots to splash. Press **BOOT button** (GPIO0) to cycle to Usage → Bluetooth → back. Press **GPIO7 capacitive pad** to cycle animations on the splash screen.

The Clawd animations come from [claudepix](https://claudepix.vercel.app) by [@amaanbuilds](https://x.com/amaanbuilds).

## Prerequisites

- macOS (this port) or Linux (original)
- [PlatformIO CLI](https://docs.platformio.org/en/latest/core/installation/index.html)
- Python 3 + `bleak` (`pip3 install bleak`)
- Claude Code with an active subscription (claude.ai OAuth)

## Flash the firmware

```bash
cd firmware
pio run -e vocat_v12 -t upload --upload-port /dev/cu.usbmodem101
```

## macOS daemon

The daemon reads your Claude Code OAuth token from the macOS Keychain (set automatically by Claude Code), polls the Anthropic API every 60 seconds, and sends usage data to the ESP32 over BLE.

### Run once

```bash
python3 daemon/claude-usage-daemon-macos.py
```

### Run at login (LaunchAgent)

```bash
cp daemon/com.clawdmeter.daemon.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.clawdmeter.daemon.plist
```

Logs: `tail -f ~/Library/Logs/clawdmeter-daemon.log`

Stop: `launchctl unload ~/Library/LaunchAgents/com.clawdmeter.daemon.plist`

### Linux daemon (original)

See the [original repo](https://github.com/HermannBjorgvin/Clawdmeter) for the Linux `bluetoothctl`-based shell daemon and systemd unit.

## BLE protocol

Same as the original — custom GATT service alongside standard HID keyboard:

| | UUID |
|---|---|
| **Data Service** | `4c41555a-4465-7669-6365-000000000001` |
| RX (write) | `4c41555a-4465-7669-6365-000000000002` |
| TX (notify) | `4c41555a-4465-7669-6365-000000000003` |
| **HID Service** | `00001812-0000-1000-8000-00805f9b34fb` |

JSON payload: `{"s":22,"sr":60,"w":16,"wr":5320,"st":"allowed","ok":true}`

## Physical buttons

| Button | GPIO | Function |
|---|---|---|
| BOOT | GPIO 0 | Space (voice-mode push-to-talk) / cycle screens |
| Cap pad 1 | GPIO 6 | Shift+Tab (mode toggle) |
| Cap pad 2 | GPIO 7 | Cycle screens / animations |

## How it works

1. The macOS daemon reads your Claude Code OAuth token from the macOS Keychain (`Claude Code-credentials` service).
2. Makes a minimal API call to `api.anthropic.com/v1/messages` (one token of Haiku).
3. Usage numbers come from response headers (`anthropic-ratelimit-unified-5h-utilization` etc.).
4. Sends JSON payload to the ESP32 over BLE GATT.
5. Firmware parses it and updates the LVGL dashboard.
6. Splash animations auto-rotate every 20 s within the current usage-rate mood group.

## Credits

- **[Clawdmeter](https://github.com/HermannBjorgvin/Clawdmeter)** by [@hermannbjorgvin](https://github.com/HermannBjorgvin) — original project this port is based on
- Pixel-art Clawd animation by [@amaanbuilds](https://x.com/amaanbuilds), from [claudepix.vercel.app](https://claudepix.vercel.app)
- [Lucide](https://lucide.dev) icons (MIT) for bluetooth and battery glyphs
- Anthropic brand fonts (Tiempos Text, Styrene B) — see licensing note below

## Licensing

Same caveat as the original: this project uses Anthropic brand fonts and the Clawd mascot without explicit permission. The code itself is offered as-is with no formal license. **Fork/copy at your own discretion.**
