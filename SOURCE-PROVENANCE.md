# Source Provenance for Armada-Dodge Peridot

This document tracks all upstream sources used in this port, adapted from armada-dodge for OnePlus 13.

## Primary Sources

### Armada-Dodge (Base Project)
- **Repository**: https://github.com/faridbtw/armada-dodge
- **Commit**: Latest main branch
- **License**: Mixed (GPL-2.0, MIT, BSD, proprietary firmware)
- **Components Used**:
  - Thermal guard architecture (Python daemons)
  - Boot scripts (RAM media assembly, UEFI boot)
  - Device tree structure and patches
  - Documentation templates

### XNU Kernel Peridot (Hardware Reference)
- **Repository**: https://github.com/slayedkaito/xnu-kernel-peridot-amiaxf
- **Commit**: Latest main branch (amiaxf fork)
- **License**: APSL-2.0, MIT, BSD
- **Hardware Details Sourced**:
  - SM8635 register addresses (TSENS, GPU, Display, Touch, etc.)
  - CPU topology (3 clusters: A520/A720/X4)
  - Power management (RPMh rails, GDSCs)
  - Pinmux configurations (TLMM)
  - Firmware loading sequences
  - Device tree bindings

### Linux Kernel (Upstream)
- **Version**: 6.12+ (recommended for SM8635 support)
- **Repository**: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git
- **License**: GPL-2.0-only
- **Subsystems Used**:
  - MSM DRM/GPU driver (drivers/gpu/drm/msm/)
  - ath11k WiFi driver (drivers/net/wireless/ath/ath11k/)
  - QUPv3 SPI/I2C/UART drivers
  - TSENS thermal driver
  - SCMI/CPPC cpufreq driver
  - RPMh power management
  - Goodix touchscreen driver (reference)

### Armada OS (Userspace)
- **Repository**: https://github.com/faridbtw/armada
- **Commit**: 20261109.dfed5d6 (pinned)
- **License**: Mixed (GPL, MIT, Apache-2.0, proprietary)
- **OCI Manifest SHA256**: 0f0c9908...
- **Source Commit**: b031deef...

### Arch Linux ARM (Host Userspace)
- **Repository**: https://github.com/archlinuxarm/PKGBUILDs
- **Kernel Package**: linux-aarch64 6.12+
- **License**: GPL-2.0, various

## Patches Applied

### From Armada-Dodge (adapted for SM8635)
| Patch | Source | Purpose |
|-------|--------|---------|
| 0049-drm-msm-add-adreno-735-peridot.patch | armada-dodge | Add Adreno 735 support to MSM DRM |
| 0050-drm-msm-peridot-panel-dsc.patch | armada-dodge | Panel DSC support |
| 0051-input-goodix-gt9916r-peridot.patch | armada-dodge | Goodix GT9916R SPI driver |
| 0052-wifi-ath11k-wcn6750-peridot.patch | armada-dodge | WCN6750 WiFi support |
| 0053-bt-qca-wcn6750-peridot.patch | armada-dodge | WCN6750 Bluetooth H4 UART |

### From Linux Omarchy Mobile
- **Repository**: https://github.com/omarchy/linux-omarchy-mobile
- **Commit**: 6cc4b65d...
- **Patches**: Panel, Bluetooth, MDSS wake fixes

## Firmware Sources (Device-Specific, Not Included)

All firmware files must be extracted from the device's vendor partition:

| Firmware | Source Path | License |
|----------|-------------|---------|
| Adreno 735 (a660_*.mdt/.bin/.fw) | /vendor/firmware_mnt/image/ | Proprietary (Qualcomm) |
| WCN6750 WiFi (ath11k) | /vendor/firmware_mnt/image/ath11k/ | Proprietary (Qualcomm) |
| WCN6750 BT (qca/btfw32.*) | /vendor/firmware_mnt/image/qca/ | Proprietary (Qualcomm) |
| Goodix GT9916R | /vendor/firmware_mnt/image/goodix/ | Proprietary (Goodix) |
| Panel firmware | /vendor/firmware_mnt/image/ | Proprietary (Panel vendor) |

## Device Tree Sources

| File | Origin |
|------|--------|
| sm8635.dtsi | Adapted from qcom SM8635 SoC DT + xnu-kernel-peridot |
| sm8635-peridot.dtsi | Peridot-specific overlay (this project) |
| sm8635-peridot.dts | Main device tree (this project) |
| sm8635-thermal.dtsi | Adapted from armada-dodge + xnu-kernel-peridot TSENS data |
| sm8635-gpu.dtsi | Adapted from armada-dodge + xnu-kernel-peridot GPU addresses |
| sm8635-display.dtsi | Adapted from armada-dodge + xnu-kernel-peridot display data |
| sm8635-touch.dtsi | From xnu-kernel-peridot Goodix SPI config |
| sm8635-wifi-bt.dtsi | From xnu-kernel-peridot WCN6750 config |

## Build Toolchain

| Tool | Version | Source |
|------|---------|--------|
| LLVM/Clang | 18+ | https://github.com/llvm/llvm-project |
| LLD | 18+ | LLVM |
| GNU Make | 4.4+ | https://www.gnu.org/software/make/ |
| aarch64-linux-gnu-gcc | 13+ | https://toolchains.bootlin.com/ |
| Python | 3.10+ | https://www.python.org/ |
| dtc | 1.7+ | https://git.kernel.org/pub/scm/utils/dtc/dtc.git |

## Verification

All source files in this repository have corresponding SHA256 hashes recorded in `SOURCE-MANIFEST.json` (to be generated after build).

## Attribution

This project stands on the shoulders of giants:
- **Armada-Dodge** by faridbtw - The RAM boot desktop architecture
- **XNU Kernel Peridot** by slayedkaito/amiaxf - SM8635 hardware reverse engineering
- **Linux Kernel Community** - Upstream drivers and infrastructure
- **Omarchy Mobile** - Mobile Linux patches
- **PostmarketOS/pmOS** - Device packaging patterns
- **LineageOS/AOSP** - Vendor firmware extraction methods