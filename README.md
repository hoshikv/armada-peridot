# Armada on OnePlus 13 (`dodge`)

Experimental **RAM-only** Armada desktop bring-up for OnePlus 13 / Qualcomm SM8750. The tested build runs Plasma 6.8.2 on native Wayland with Adreno 830 compositing, touchscreen input, Wi-Fi, Bluetooth discovery and a 120 Hz display mode.

[Quickstart](QUICKSTART.md) · [Build notes](docs/BUILDING.md) · [Thermal control](docs/THERMAL.md) · [Validation](validation/thermal-build.json) · [Sources and credits](SOURCE-PROVENANCE.md)

This is a source snapshot and a set of bring-up recipes, **not a downloadable OS image or a complete standalone image builder**. Prepared RAM images, firmware, device calibration, system roots, SDKs and private device logs are not included. The original working workspace is preserved separately.

## Verified state

| Component | Result |
| --- | --- |
| Desktop | Native KWin Wayland, Plasma 6.8.2, 150% scaling, portrait |
| Graphics | Adreno 830, OpenGL ES/EGL compositing; GPU capped at 222 MHz |
| Display | 1440×3168 at 120 Hz; application FPS not measured |
| Touch and keyboard | Touch works; Plasma Keyboard appears and types |
| Wi-Fi | Connected through KDE by the user |
| Bluetooth | Controller powered; nearby-device discovery works; pairing unverified |
| Buttons | Power toggles display off/on; volume key events verified |
| CPU | All eight cores; schedutil; six capped at 1.3632 GHz, two at 1.4016 GHz |
| Thermal control | 16 CPU and 8 GPU sensors, SCMI frequency control and kernel CPU cooling |
| USB recovery | Fixed-command CDC service and cold reboot to Android |
| Steam | Native ARM Big Picture first-run screen visible; touch works; further setup deferred |

Speaker audio is deferred. Deep suspend, Bluetooth pairing, games/Proton and battery/skin/charging thermal management are unverified. Experimental thermal controls are not equivalent to Android's validated thermal management.

## Thermal policy

The image starts with one CPU. It enables all eight and starts the desktop only after sensors, both performance policies and cooling bindings pass checks. Internal chip-temperature limits are:

| Temperature | Action |
| --- | --- |
| Normal | CPU ceilings 1.3632 / 1.4016 GHz |
| 70°C | Ceilings 960 MHz / 1.0176 GHz |
| 80°C | Firmware minimums 384 MHz / 1.0176 GHz |
| 85°C | Cold reboot to Android |

A separate watchdog monitors the guard's heartbeat. Runtime sensor or control failures also request recovery. A **simulated 75°C reading**, without physical heating, verified both the guard's reduced frequency limits and kernel cooling activation; normal limits returned after resetting emulation. The 80°C/85°C policy branches were unit-tested, not tested by physically heating the phone.

## Layout

- `experimental/armada-thermal-v1/`: current guard, watchdog, device-tree recipe and tests.
- `experimental/armada-steam-v1/`: current image assembly and native Steam setup.
- Other `experimental/` directories: the dependency chain and earlier desktop, touch, USB and hardware recipes.
- `source/linux/`: source slices used for the tested DRM/MSM, ath12k and Bluetooth modules.
- `source/modules/`: display, clock and power-provider module sources.
- `patches/`: attributed Armada and Dodge kernel changes.
- `tools/`: RAM boot, FAT media construction and device-tree helpers.
- `validation/`: curated build facts without raw device captures.

Run the host thermal policy tests without connecting a phone:

```sh
python3 experimental/armada-thermal-v1/test-thermal.py
```

For booting and required local inputs, read the [quickstart](QUICKSTART.md) and [build notes](docs/BUILDING.md). There are no flash, erase or partition-install steps in the boot workflow.
