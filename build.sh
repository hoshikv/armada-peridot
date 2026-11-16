#!/bin/bash
# Build script for Armada-Dodge Peridot
# Orchestrates the complete build process

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${WORKSPACE:-/home/hoshikava/peridot-workspace}"
KERNEL_VERSION="${KERNEL_VERSION:-6.12}"
JOBS="${JOBS:-$(nproc)}"

# Toolchain
export LLVM="${LLVM:-/opt/homebrew/opt/llvm/bin}"
export LD="${LD:-/opt/homebrew/bin/ld.lld}"
export CROSS_COMPILE="${CROSS_COMPILE:-aarch64-linux-gnu-}"
export ARCH=arm64

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[BUILD]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# Check prerequisites
check_prereqs() {
    log "Checking prerequisites..."
    command -v clang >/dev/null || { error "clang not found"; exit 1; }
    command -v ld.lld >/dev/null || { error "ld.lld not found"; exit 1; }
    command -v aarch64-linux-gnu-gcc >/dev/null || { error "aarch64-linux-gnu-gcc not found"; exit 1; }
    command -v dtc >/dev/null || { error "dtc not found"; exit 1; }
    command -v python3 >/dev/null || { error "python3 not found"; exit 1; }
    command -v fastboot >/dev/null || { error "fastboot not found"; exit 1; }
    command -v adb >/dev/null || { error "adb not found"; exit 1; }
    log "Prerequisites OK"
}

# Setup workspace
setup_workspace() {
    log "Setting up workspace: $WORKSPACE"
    mkdir -p "$WORKSPACE"/{armada-root,arch-root,steam-extra,kernel-headers,firmware,modules}
}

# Build kernel
build_kernel() {
    log "Building Linux kernel $KERNEL_VERSION..."
    cd "$WORKSPACE"
    
    if [ ! -d "linux-$KERNEL_VERSION" ]; then
        log "Cloning Linux kernel..."
        git clone --depth 1 --branch "v$KERNEL_VERSION" \
            https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git "linux-$KERNEL_VERSION"
    fi
    
    cd "linux-$KERNEL_VERSION"
    
    # Apply patches
    log "Applying Peridot patches..."
    for patch in "$SCRIPT_DIR/patches/armada"/*.patch; do
        if [ -f "$patch" ]; then
            git apply "$patch" 2>/dev/null || warn "Patch $(basename "$patch") may need manual apply"
        fi
    done
    
    # Configure
    log "Configuring kernel..."
    make ARCH=arm64 CROSS_COMPILE="$CROSS_COMPILE" defconfig
    
    # Enable Peridot configs
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
    
    make ARCH=arm64 CROSS_COMPILE="$CROSS_COMPILE" olddefconfig
    
    # Build
    log "Compiling kernel and modules..."
    make -j"$JOBS" ARCH=arm64 CROSS_COMPILE="$CROSS_COMPILE" \
        LLVM="$LLVM" LD="$LD" \
        KCPPFLAGS="-Wno-error=unused-variable" \
        Image
    
    make -j"$JOBS" ARCH=arm64 CROSS_COMPILE="$CROSS_COMPILE" \
        LLVM="$LLVM" LD="$LD" \
        M=drivers/gpu/drm/msm \
        M=drivers/net/wireless/ath/ath11k \
        M=drivers/input/touchscreen \
        M=drivers/bluetooth \
        modules
    
    # Install headers
    log "Installing kernel headers..."
    make ARCH=arm64 CROSS_COMPILE="$CROSS_COMPILE" \
        INSTALL_HDR_PATH="$WORKSPACE/kernel-headers" headers_install
    
    # Install modules
    log "Installing modules..."
    make ARCH=arm64 CROSS_COMPILE="$CROSS_COMPILE" \
        INSTALL_MOD_PATH="$WORKSPACE/modules" modules_install
    
    # Copy artifacts
    cp arch/arm64/boot/Image "$WORKSPACE/Image"
    log "Kernel build complete"
}

# Build DTB
build_dtb() {
    log "Building device tree..."
    dtc -I dts -O dtb -o "$WORKSPACE/peridot.dtb" \
        "$SCRIPT_DIR/source/linux/arch/arm64/boot/dts/qcom/sm8635-peridot.dts"
    log "DTB built: $WORKSPACE/peridot.dtb"
}

# Build initrd
build_initrd() {
    log "Building initrd..."
    local INITRD_DIR="$WORKSPACE/initrd-build"
    rm -rf "$INITRD_DIR"
    mkdir -p "$INITRD_DIR"/{bin,sbin,etc,lib,lib64,usr/bin,usr/sbin,usr/lib,usr/lib64,proc,sys,dev,run,thermal}
    
    # Copy thermal scripts
    cp "$SCRIPT_DIR/experimental/peridot-thermal-v1/thermal-guard.py" "$INITRD_DIR/thermal/"
    cp "$SCRIPT_DIR/experimental/peridot-thermal-v1/thermal-watchdog.py" "$INITRD_DIR/thermal/"
    
    # Copy kernel modules
    local KVER=$(ls "$WORKSPACE/modules/lib/modules/" | head -1)
    cp -r "$WORKSPACE/modules/lib/modules/$KVER" "$INITRD_DIR/lib/modules/"
    
    # Copy firmware
    mkdir -p "$INITRD_DIR/lib/firmware"
    cp -r "$WORKSPACE/firmware"/* "$INITRD_DIR/lib/firmware/" 2>/dev/null || true
    
    # Create init script
    cat > "$INITRD_DIR/init" <<'EOF'
#!/bin/busybox sh
mount -t proc none /proc
mount -t sysfs none /sys
mount -t devtmpfs none /dev
mount -t tmpfs none /run

modprobe qcom_tsens
modprobe qcom_spmi_temp_alarm

/thermal/thermal-guard.py &
/thermal/thermal-watchdog.py &

modprobe msm_drm
modprobe panel_xiaomi_peridot
modprobe goodix
modprobe ath11k_pci
modprobe hci_uart
modprobe qca

exec /sbin/init
EOF
    chmod +x "$INITRD_DIR/init"
    
    # Create initrd
    cd "$INITRD_DIR"
    find . -print0 | cpio --null -ov --format=newc | gzip -9 > "$WORKSPACE/initrd.img"
    log "Initrd built: $WORKSPACE/initrd.img"
}

# Build media image
build_media() {
    log "Building FAT media image..."
    python3 "$SCRIPT_DIR/tools/make-peridot-efi-media.py" \
        --armada-root "$WORKSPACE/armada-root" \
        --arch-root "$WORKSPACE/arch-root" \
        --steam-extra "$WORKSPACE/steam-extra" \
        --modules-dir "$WORKSPACE/modules/lib/modules/$(ls "$WORKSPACE/modules/lib/modules/" | head -1)" \
        --firmware-dir "$WORKSPACE/firmware" \
        --dtb "$WORKSPACE/peridot.dtb" \
        --initrd "$WORKSPACE/initrd.img" \
        --kernel "$WORKSPACE/Image" \
        --output "$WORKSPACE/peridot-media.img"
    log "Media image built: $WORKSPACE/peridot-media.img"
}

# Main
main() {
    log "Starting Armada-Dodge Peridot build"
    log "Workspace: $WORKSPACE"
    log "Kernel: $KERNEL_VERSION"
    log "Jobs: $JOBS"
    
    check_prereqs
    setup_workspace
    
    # Check required inputs exist
    for dir in "$WORKSPACE/armada-root" "$WORKSPACE/arch-root" "$WORKSPACE/steam-extra" "$WORKSPACE/firmware"; do
        if [ ! -d "$dir" ] || [ -z "$(ls -A "$dir")" ]; then
            warn "Directory $dir is empty or missing - please populate it first"
        fi
    done
    
    build_kernel
    build_dtb
    build_initrd
    build_media
    
    log "Build complete!"
    log "Artifacts in $WORKSPACE:"
    ls -lh "$WORKSPACE"/{Image,initrd.img,peridot.dtb,peridot-media.img} 2>/dev/null || true
    log ""
    log "To boot:"
    log "  1. fastboot boot <uefi.fd>"
    log "  2. Use UEFI to load media/DTB/kernel/initrd"
    log "  3. Or use: python3 tools/boot-peridot-armada.py --uefi <uefi.fd> --media $WORKSPACE/peridot-media.img --dtb $WORKSPACE/peridot.dtb --initrd $WORKSPACE/initrd.img --kernel $WORKSPACE/Image"
}

# Handle arguments
case "${1:-all}" in
    all)
        main
        ;;
    kernel)
        check_prereqs
        setup_workspace
        build_kernel
        ;;
    dtb)
        build_dtb
        ;;
    initrd)
        build_initrd
        ;;
    media)
        build_media
        ;;
    clean)
        log "Cleaning..."
        rm -rf "$WORKSPACE"/{Image,initrd.img,peridot.dtb,peridot-media.img,modules,kernel-headers,initrd-build,linux-$KERNEL_VERSION}
        log "Clean complete"
        ;;
    *)
        echo "Usage: $0 {all|kernel|dtb|initrd|media|clean}"
        exit 1
        ;;
esac