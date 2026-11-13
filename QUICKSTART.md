# RAM boot quickstart

## Requirements

- OnePlus 13 (`dodge`, SM8750) with an already unlocked bootloader.
- A prepared compatible Project Boot UEFI image and Armada RAM media image.
- Python 3, Android platform-tools (`adb`, `fastboot`), a USB cable, and the matching local build profile.

The images and firmware are not distributed here. A fresh source checkout cannot boot until you supply those local inputs. The tested packaging/boot host is macOS; it uses Homebrew tool paths in parts of the original recipes.

## Boot a prepared build

1. Put your prepared files in ignored `local/armada-thermal.img` and `local/dodge-uefi.img`.
2. Review `experimental/armada-thermal-v1/STATUS.json`. Its SHA256 values describe the owner's tested build. For a rebuild, make an ignored `local/STATUS.json` with your actual image hashes and paths. Image paths are relative to this checkout and must remain inside it.
3. Check files without contacting the phone:

   ```sh
   python3 tools/boot-op13-armada.py --check
   # For your own profile:
   python3 tools/boot-op13-armada.py --profile local/STATUS.json --check
   ```

4. Start Android, connect USB, and obtain your native device serial with `adb devices`. Then:

   ```sh
   python3 tools/boot-op13-armada.py --serial YOUR_PHONE_SERIAL
   # Or add --profile local/STATUS.json for your prepared build.
   ```

Keep USB connected through upload. The helper validates checksums, RAM-boots UEFI, stages the FAT media, arms the touch preparation and launches Linux. It then checks USB recovery, synchronizes the RAM clock and waits for live thermal monitoring. A reachable existing RAM session is restarted automatically. Run only one boot/USB tool at a time.

The custom UEFI must support the Linux FDT, touch preparation and recovery commands used by this helper; an arbitrary generic UEFI image is insufficient.

## In the desktop

- Scaling is 150%, portrait, with the 120 Hz panel mode.
- Tap text fields for Plasma Keyboard. Fastfetch is available in the startup terminal.
- Reconnect Wi-Fi through KDE after each reboot. Enter passwords on the phone.
- Short-press power to turn the display off; press again to turn it back on.
- Bluetooth discovery and volume key events work. Speaker audio remains deferred.
- Steam Big Picture can open after Wi-Fi connects. Its first-run screen and touch were verified; further setup is deferred. When ready, choose your timezone and complete any sign-in yourself. Games/Proton are unverified.

## Thermal status and recovery

On macOS, the fixed-command client locates the identified USB serial port:

```sh
python3 experimental/armada-thermal-v1/control-phone.py thermalstatus
python3 experimental/armada-thermal-v1/control-phone.py status
python3 experimental/armada-thermal-v1/control-phone.py reboot
```

The last command cold-reboots to Android. If recovery USB is unavailable, manually restart into Android and reconnect. Do not substitute flashing commands.

The guard throttles at 70/80°C and requests Android recovery at 85°C or runtime monitoring failure. See [thermal details and limitations](docs/THERMAL.md). Older fallback profiles do not include these verified thermal controls.

## Persistence

The OS runs in RAM. Rebooting loses session changes, downloads, network credentials and pairings. The kernel configuration used for the tested port disables the phone's UFS controller/PHY; the workflow does not mount internal phone filesystems. Android resumes its ordinary storage behavior when booted normally.
