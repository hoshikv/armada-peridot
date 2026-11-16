# Quick Start: Armada-Dodge Peridot

RAM-boot a native Wayland desktop on Xiaomi POCO F6 / Redmi Turbo 3 (peridot, SM8635).

**No flash/install** — runs entirely in RAM; rebooting returns to Android.

## Prerequisites

### Host (macOS tested, Linux should work)
- Python 3.10+
- `dtc` (device tree compiler)
- LLVM/Clang + `ld.lld` (for cross-compilation)
- `aarch64-linux-gnu-` cross toolchain
- Android platform-tools (`adb`, `fastboot`)
- GNU `make`

### Device
- Xiaomi POCO F6 / Redmi Turbo 3 (peridot)
- Unlocked bootloader
- **Custom UEFI** with RAM media/FDT/touch lease/USB CDC recovery support (equivalent to Project Boot for OnePlus 13)

### Local Workspace (prepare beforehand)
```
$WORKSPACE/
├── armada-root/              # Armada OS userspace (OCI extracted)
├── arch-root/                # Arch Linux ARM userspace
├── steam-extra/              # Steam client overlay files
├── kernel-headers/           # Exact generated headers (Linux 6.12+)
├── firmware/
│   ├── display/              # Panel firmware (if needed)
│   ├── gpu/                  # Adreno 735 firmware (a660_*.mdt/.bin/.fw)
│   ├── wifi/                 # WCN6750 firmware (ath11k)
│   ├── bt/                   # WCN6750 BT firmware
│   └── touch/                # Goodix GT9916R firmware
├── peridot.dtb               # Device tree blob for Peridot
├── initrd.img                # Base initrd
└── uefi.fd                   # Custom UEFI payload
```

## Build Kernel Modules

```bash
# Set up environment
export HEADERS="$WORKSPACE/kernel-headers"
export CROSS_COMPILE=aarch64-linux-gnu-
export LLVM=/opt/homebrew/opt/llvm/bin
export LD=/opt/homebrew/bin/ld.lld

# MSM DRM/GPU driver
make -C "$HEADERS" M=source/linux/drivers/gpu/drm/msm \
  ARCH=arm64 LLVM="$LLVM" LD="$LD" \
  CROSS_COMPILE="$CROSS_COMPILE" HOSTCC=clang \
  KCPPFLAGS="-Wno-error=unused-variable"

# ath11k WiFi driver
make -C "$HEADERS" M=source/linux/drivers/net/wireless/ath/ath11k \
  ARCH=arm64 LLVM="$LLVM" LD="$LD" \
  CROSS_COMPILE="$CROSS_COMPILE" HOSTCC=clang

# Clock/power provider modules
make -C "$HEADERS" M=source/modules/providers \
  ARCH=arm64 LLVM="$LLVM" LD="$LD" \
  CROSS_COMPILE="$CROSS_COMPILE" HOSTCC=clang
```

## Assemble RAM Media

```bash
cd /home/hoshikava/armada-dodge-peridot
python3 tools/make-peridot-efi-media.py \
  --armada-root "$WORKSPACE/armada-root" \
  --arch-root "$WORKSPACE/arch-root" \
  --steam-extra "$WORKSPACE/steam-extra" \
  --modules-dir /path/to/built/modules \
  --firmware-dir "$WORKSPACE/firmware" \
  --dtb "$WORKSPACE/peridot.dtb" \
  --initrd "$WORKSPACE/initrd.img" \
  --output "$WORKSPACE/peridot-media.img"
```

## Boot

```bash
# Boot custom UEFI (fastboot boot)
fastboot boot "$WORKSPACE/uefi.fd"

# In UEFI shell, load RAM media and boot Linux
# (UEFI must support: load FDT, touch lease, USB CDC recovery, chain to Linux)

# Or use the boot helper script:
python3 tools/boot-peridot-armada.py \
  --uefi "$WORKSPACE/uefi.fd" \
  --media "$WORKSPACE/peridot-media.img" \
  --dtb "$WORKSPACE/peridot.dtb"
```

## What Works After Boot

- KWin/Plasma Wayland desktop at 120 Hz
- GPU acceleration (Adreno 735, OpenGL ES/EGL)
- Touchscreen (multitouch)
- WiFi (ath11k)
- Bluetooth (H4 UART)
- Hardware buttons (power, volume)
- Thermal management (81 zones, SCMI DVFS, cooling trips)

## Deferred / Not Working

- Speaker audio
- Deep suspend
- Bluetooth pairing (may need userspace agent)
- Battery/charging/skin thermal management
- Gaming/Proton
- Internal storage access (UFS disabled in DT)

## Troubleshooting

### Thermal guard not starting
- Verify `qcom_tsens` and `qcom-spmi-temp-alarm` modules loaded
- Check SCMI mailbox at `0x17A20000` (APPS RSC)
- Ensure UEFI exposes thermal zones via FDT

### Touch not working
- Verify Goodix firmware leased from UEFI
- Check SPI pins: MISO=16, MOSI=17, CLK=18, CS=19
- Ensure kernel SPI node for QUPv3 SE4 is **disabled** in DT
- Try `touch_no_rpmh=1` boot arg

### GPU not initializing
- Verify Adreno 735 firmware (a660_zap.mdt, a660_gmu.bin, a660_sqe.fw)
- Check GPU CC at `0x03D90000`, GMU at `0x03D68000`
- Ensure SMMU at `0x03DA0000` configured

### WiFi not working
- Verify WCN6750 firmware loaded
- Check PCIe link for WPSS at `0x9BB00000`
- Ensure ath11k driver matches firmware version