# Armada-Dodge Peridot

Experimental RAM-only desktop bring-up for **Xiaomi POCO F6 / Redmi Turbo 3** (codename: **peridot**, SoC: **SM8635** / Snapdragon 8s Gen 3).

Based on [armada-dodge](https://github.com/faridbtw/armada-dodge) for OnePlus 13 (SM8750), adapted for Peridot (SM8635).

## Status

| Component | Status | Notes |
|-----------|--------|-------|
| CPU (8 cores: 3×A520 + 4×A720 + 1×X4) | ✅ Planned | PSCI + cpufreq via SCMI |
| GPU (Adreno 735) | ✅ Planned | Chip ID 0x43030B00, catalog needed |
| Display (MIPI DSI, 1220×2712@120Hz) | ✅ Planned | Panel driver TBD |
| Touchscreen (Goodix GT9916R, SPI) | ✅ Planned | QUPv3 SE4, GPIO bitbang fallback |
| WiFi (WCN6750, ath11k) | ✅ Planned | PCIe + QMI |
| Bluetooth (WCN6750, H4 UART) | ✅ Planned | QUPv3 SE2 |
| Thermal (3× TSENS blocks) | ✅ Planned | 81 zones, SCMI DVFS |
| Storage (UFS) | ❌ Deferred | UFS disabled in DT for RAM boot |
| Audio (ADSP) | ❌ Deferred | Not in scope for desktop |
| Deep suspend | ❌ Deferred | |
| Battery/charging thermal | ❌ Deferred | |

## Key Differences from OnePlus 13 (SM8750)

| Aspect | OnePlus 13 (SM8750) | Peridot (SM8635) |
|--------|---------------------|------------------|
| CPU | 8× Oryon (2 clusters) | 8 cores, 3 clusters (A520/A720/X4) |
| GPU | Adreno 830 (0x44050000) | Adreno 735 (0x43030B00) |
| Thermal | 4 TSENS blocks | 3 TSENS blocks |
| Touch | S3910 (SPI bitbang) | Goodix GT9916R (SPI + I2C) |
| WiFi/BT | WCN7860 (ath12k) | WCN6750 (ath11k) |
| Display | AA569 (DSC, cmd mode) | TBD (likely DSC, video mode) |
| Boot CPU | Core 0 | Core 7 (prime/X4) |

## Hardware Addresses (from xnu-kernel-peridot)

### Thermal (TSENS)
- TSENS0: `0x0C222000`
- TSENS1: `0x0C223000`
- TSENS2: `0x0C224000` (Peridot-specific)

### GPU (Adreno 735)
- GPU CC: `0x03D90000` (size `0xA000`)
- GMU: `0x03D68000` (size `0x37000`)
- GBIF: `0x03D0F000`
- SMMU: `0x03DA0000` (size `0x40000`)
- GCC: `0x00100000`

### Touchscreen (Goodix GT9916R)
- SPI: QUPv3 SE4 @ `0x00A90000`
- GPIOs: MISO=16, MOSI=17, CLK=18, CS=19, INT=129, RESET=128
- LDOB23 (1.8V) + LDOB13 (3.3V) via RPMh

### Other
- BLUETOOTH UART: QUPv3 SE2 @ `0x00888000`
- WPSS (WiFi): `0x9BB00000` (25MB)
- ADSP: `0x9D400000` (56MB)
- SMEM: `0x81D00000` (2MB)

## Requirements (not included)

- Armada userspace root (from [armada](https://github.com/faridbtw/armada))
- Arch Linux ARM userspace
- Device-specific firmware (display, GPU, WiFi, BT, touch)
- Custom UEFI with RAM media/FDT/touch/USB recovery (from ios-dodge equivalent)
- Exact kernel headers (Linux 6.12+ recommended for SM8635)

## Quick Start

See [QUICKSTART.md](QUICKSTART.md) for RAM boot instructions.

## Building

See [docs/BUILDING.md](docs/BUILDING.md) for build notes and dependency chain.

## Source Provenance

See [SOURCE-PROVENANCE.md](SOURCE-PROVENANCE.md) for sources and credits.

## License

This project aggregates code from multiple upstream sources with their respective licenses. See [licenses/](licenses/) for details.