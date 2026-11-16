# Building Armada-Dodge Peridot

Complete build instructions for the Xiaomi Peridot (POCO F6 / Redmi Turbo 3) port.

## Prerequisites

### Host System (macOS or Linux)
- **macOS** (tested) with Homebrew, or **Linux** (Ubuntu 22.04+, Arch, Fedora)
- **Disk Space**: 50GB+ free
- **RAM**: 16GB+ recommended

### Required Packages

#### macOS (Homebrew)
```bash
brew install python3 llvm lld make dtc git wget xz
brew install --cask android-platform-tools
# Cross-compiler
brew install aarch64-linux-gnu-gcc  # or use bootlin toolchain
```

#### Linux (Ubuntu/Debian)
```bash
sudo apt update && sudo apt install -y \
    python3 python3-venv \
    clang lld llvm \
    make dtc git wget xz-utils \
    android-sdk-platform-tools \
    gcc-aarch64-linux-gnu g++-aarch64-linux-gnu \
    libssl-dev bc flex bison libelf-dev
```

#### Linux (Arch)
```bash
sudo pacman -S python clang lld llvm make dtc git android-tools \
    aarch64-linux-gnu-gcc aarch64-linux-gnu-binutils \
    base-devel
```

### Toolchain Setup

Use LLVM/Clang with LLD for cross-compilation (matching armada-dodge):

```bash
export LLVM=/opt/homebrew/opt/llvm/bin  # macOS
export LLVM=/usr/bin                    # Linux
export LD=/opt/homebrew/bin/ld.lld      # macOS
export LD=/usr/bin/ld.lld               # Linux
export CROSS_COMPILE=aarch64-linux-gnu-
export ARCH=arm64
```

## Workspace Preparation

Create workspace directory structure:

```bash
export WORKSPACE=/path/to/peridot-workspace
mkdir -p $WORKSPACE/{armada-root,arch-root,steam-extra,kernel-headers,firmware}
```

### 1. Armada Userspace
```bash
# Extract Armada OCI image (from armada-dodge SOURCE-PROVENANCE)
# This requires the Armada OS build or prebuilt OCI
cd $WORKSPACE
# TODO: Add extraction script
```

### 2. Arch Linux ARM Userspace
```bash
# Use arch-bootstrap or extract from Arch Linux ARM rootfs
cd $WORKSPACE
wget http://os.archlinuxarm.org/os/ArchLinuxARM-aarch64-latest.tar.gz
mkdir arch-root && tar -xzf ArchLinuxARM-aarch64-latest.tar.gz -C arch-root
```

### 3. Steam Overlay
```bash
# Extract Steam client from Flatpak or native package
mkdir -p $WORKSPACE/steam-extra
# TODO: Add extraction
```

### 4. Kernel Headers (CRITICAL - Must Match Running Kernel)
```bash
# Build kernel first, then install headers
# Or extract from Arch Linux ARM kernel package
cd $WORKSPACE
# The exact kernel version must match what you'll run
pacman -Sw linux-aarch64-headers  # Download package
# Extract to kernel-headers/
```

### 5. Firmware Extraction (from Device)
```bash
# On device with root:
adb root
adb pull /vendor/firmware_mnt/image $WORKSPACE/firmware/

# Required firmware:
# - Adreno 735: a660_zap.mdt, a660_gmu.bin, a660_sqe.fw
# - WCN6750 WiFi: ath11k/WCN6750/hw2.0/{firmware.bin,board.bin,board-2.bin}
# - WCN6750 BT: qca/btfw32.tlv, qca/btfw32.cfg
# - Goodix GT9916R: goodix/*.fw
# - Panel: panel/*.fw
```

## Building Kernel Modules

### Kernel Source
```bash
cd $WORKSPACE
git clone --depth 1 --branch v6.12 https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git linux-6.12
cd linux-6.12
```

### Apply Patches
```bash
# Apply Peridot patches from this repo
for patch in /path/to/armada-dodge-peridot/patches/armada/*.patch; do
    git apply "$patch" || echo "Patch $patch failed (may need manual apply)"
done
```

### Configure Kernel
```bash
# Use Peridot defconfig as base
make ARCH=arm64 CROSS_COMPILE=$CROSS_COMPILE defconfig
# Enable required modules
cat <<EOF >> .config
CONFIG_DRM_MSM=y
CONFIG_DRM_MSM_ADRENO=y
CONFIG_DRM_MSM_ADRENO_A7XX=y
CONFIG_DRM_MSM_DSI=y
CONFIG_DRM_MSM_DSI_DSC=y
CONFIG_DRM_PANEL_ORIENTATION_QUIRKS=y
CONFIG_DRM_PANEL_XIAOMI_PERIDOT=m
CONFIG_TOUCHSCREEN_GOODIX=m
CONFIG_TOUCHSCREEN_GOODIX_SPI=m
CONFIG_ATH11K=m
CONFIG_ATH11K_PCI=m
CONFIG_BT_HCIUART=m
CONFIG_BT_HCIUART_H4=y
CONFIG_BT_HCIUART_QCA=y
CONFIG_BT_QCA=m
CONFIG_QCOM_TSENS=y
CONFIG_QCOM_SPMI_TEMP_ALARM=y
CONFIG_QCOM_SCMI=y
CONFIG_QCOM_CPR=y
CONFIG_QCOM_RPMH=y
CONFIG_QCOM_GDSC=y
CONFIG_DEBUG_FS=y
EOF
make ARCH=arm64 CROSS_COMPILE=$CROSS_COMPILE olddefconfig
```

### Build Kernel and Modules
```bash
# Build kernel Image
make -j$(nproc) ARCH=arm64 CROSS_COMPILE=$CROSS_COMPILE \
    LLVM=$LLVM LD=$LD \
    KCPPFLAGS="-Wno-error=unused-variable" \
    Image

# Build modules
make -j$(nproc) ARCH=arm64 CROSS_COMPILE=$CROSS_COMPILE \
    LLVM=$LLVM LD=$LD \
    M=drivers/gpu/drm/msm \
    M=drivers/net/wireless/ath/ath11k \
    M=drivers/input/touchscreen \
    M=drivers/bluetooth \
    modules

# Install headers (for module builds against this kernel)
make ARCH=arm64 CROSS_COMPILE=$CROSS_COMPILE \
    INSTALL_HDR_PATH=$WORKSPACE/kernel-headers headers_install
```

### Copy Built Artifacts
```bash
# Kernel Image
cp arch/arm64/boot/Image $WORKSPACE/Image

# Modules
mkdir -p $WORKSPACE/modules
make ARCH=arm64 CROSS_COMPILE=$CROSS_COMPILE \
    INSTALL_MOD_PATH=$WORKSPACE/modules modules_install

# DTB (compile from this repo's DT sources)
dtc -I dts -O dtb -o $WORKSPACE/peridot.dtb \
    /path/to/armada-dodge-peridot/source/linux/arch/arm64/boot/dts/qcom/sm8635-peridot.dts
```

## Building Initrd

```bash
cd $WORKSPACE

# Create minimal initrd with thermal guard, modules, firmware
mkdir -p initrd/{bin,sbin,etc,lib,lib64,usr/bin,usr/sbin,usr/lib,usr/lib64,proc,sys,dev,run,thermal}

# Copy thermal scripts
cp /path/to/armada-dodge-peridot/experimental/peridot-thermal-v1/thermal-guard.py initrd/thermal/
cp /path/to/armada-dodge-peridot/experimental/peridot-thermal-v1/thermal-watchdog.py initrd/thermal/

# Copy kernel modules
cp -r modules/lib/modules/* initrd/lib/modules/

# Copy firmware
mkdir -p initrd/lib/firmware
cp -r firmware/* initrd/lib/firmware/

# Create init script
cat > initrd/init <<'EOF'
#!/bin/busybox sh
# Minimal init for Armada RAM boot
mount -t proc none /proc
mount -t sysfs none /sys
mount -t devtmpfs none /dev
mount -t tmpfs none /run

# Load thermal modules
modprobe qcom_tsens
modprobe qcom_spmi_temp_alarm

# Start thermal guard
/thermal/thermal-guard.py &
/thermal/thermal-watchdog.py &

# Load GPU/display modules
modprobe msm_drm
modprobe panel_xiaomi_peridot

# Load touch
modprobe goodix

# Load WiFi/BT
modprobe ath11k_pci
modprobe hci_uart
modprobe qca

# Start userspace (Armada/Arch)
exec /sbin/init
EOF
chmod +x initrd/init

# Create initrd
cd initrd
find . -print0 | cpio --null -ov --format=newc | gzip -9 > ../initrd.img
cd ..
```

## Building UEFI

The UEFI must support:
- Loading FDT from memory
- Touch firmware lease to Linux
- USB CDC recovery interface
- Chain loading Linux kernel + initrd + DTB
- FAT media mounting

See `ios-dodge` equivalent for Peridot (not in this repo).

```bash
# Placeholder - requires custom UEFI build
cp /path/to/peridot-uefi.fd $WORKSPACE/uefi.fd
```

## Assembling FAT Media

```bash
cd /path/to/armada-dodge-peridot
python3 tools/make-peridot-efi-media.py \
  --armada-root $WORKSPACE/armada-root \
  --arch-root $WORKSPACE/arch-root \
  --steam-extra $WORKSPACE/steam-extra \
  --modules-dir $WORKSPACE/modules/lib/modules/$(uname -r) \
  --firmware-dir $WORKSPACE/firmware \
  --dtb $WORKSPACE/peridot.dtb \
  --initrd $WORKSPACE/initrd.img \
  --kernel $WORKSPACE/Image \
  --output $WORKSPACE/peridot-media.img
```

## Booting

### 1. Boot UEFI via Fastboot
```bash
fastboot boot $WORKSPACE/uefi.fd
```

### 2. In UEFI Shell, Load Components
```bash
# UEFI must provide commands to:
# - Load DTB to FD_BASE (0xA7100000)
# - Load FAT media to MEDIA_BASE (0x90000000)
# - Load kernel to PAYLOAD_BASE (0xF0000000)
# - Load initrd
# - Set bootargs
# - Jump to kernel

# Example (UEFI-specific):
# load_fdt peridot.dtb
# load_media peridot-media.img
# boot_linux Image initrd.img peridot.dtb "bootargs..."
```

### 3. Or Use Boot Helper Script
```bash
python3 tools/boot-peridot-armada.py \
  --uefi $WORKSPACE/uefi.fd \
  --media $WORKSPACE/peridot-media.img \
  --dtb $WORKSPACE/peridot.dtb \
  --initrd $WORKSPACE/initrd.img \
  --kernel $WORKSPACE/Image
```

## Verification

After boot, verify via ADB:

```bash
# Thermal
adb shell pgrep -f thermal-guard
adb shell cat /var/log/thermal-guard.log

# Touch
adb shell cat /proc/bus/input/devices | grep -i goodix

# GPU
adb shell ls /sys/class/drm/
adb shell dmesg | grep -i adreno

# Display
adb shell cat /sys/class/drm/card0/modes

# WiFi
adb shell ip link show wlan0

# Bluetooth
adb shell hciconfig -a
```

## Common Issues

### Kernel Module Version Mismatch
- **Cause**: Kernel headers don't match running kernel
- **Fix**: Rebuild kernel and modules together, use exact headers

### Firmware Not Found
- **Cause**: Firmware files not in `/lib/firmware/`
- **Fix**: Ensure firmware extracted to `firmware-dir` and copied to initrd/media

### Touch Not Working
- **Cause**: SPI controller not enabled, GPIO pinmux wrong, firmware lease missing
- **Fix**: Check DTB has QUPv3 SE4 enabled, UEFI leases firmware

### GPU Not Initializing
- **Cause**: Adreno firmware missing, GMU not starting, SMMU config
- **Fix**: Verify a660_* firmware in place, check dmesg for GMU logs

### Thermal Guard Not Starting
- **Cause**: qcom_tsens module not loaded, SCMI mailbox not working
- **Fix**: Check APPS RSC initialized by UEFI, SCMI in DTB

## Clean Build

```bash
# Clean kernel
cd $WORKSPACE/linux-6.12
make ARCH=arm64 CROSS_COMPILE=$CROSS_COMPILE mrproper

# Clean workspace
rm -rf $WORKSPACE/{Image,initrd.img,peridot.dtb,peridot-media.img,modules,kernel-headers}
```

## Automation

Consider creating a build script that orchestrates all steps. The armada-dodge project uses a series of experimental recipes (`armada-ram-v1`, `armada-thermal-v1`, etc.) that can be adapted.