#!/usr/bin/env python3
"""
Boot Helper for Xiaomi Peridot (POCO F6 / Redmi Turbo 3) - Armada RAM Boot

Adapted from armada-dodge boot-op13-armada.py for OnePlus 13.
Boots custom UEFI, loads RAM media, starts Linux with thermal guard.
"""

import os
import sys
import struct
import hashlib
import subprocess
import time
import argparse
import logging
from pathlib import Path
from typing import Optional, Tuple

# ─── Configuration ────────────────────────────────────────────────

# Peridot memory layout (from xnu-kernel-peridot)
PAYLOAD_BASE = 0xF0000000       # Kernel/UEFI load address
FD_BASE = 0xA7100000            # FDT base address
FD_SIZE = 0x300000              # FDT size (3MB)
FB_BASE = 0xE3940000            # Framebuffer base (UEFI GOP)
MEDIA_BASE = 0x90000000         # FAT media load address
MEDIA_SIZE = 0x80000000         # 2GB media size

# Boot arguments for Peridot
DEFAULT_BOOTARGS = (
    "console=ttyMSM0,115200n8 earlycon=msm_geni_serial,0x888000 "
    "bootcpu=7 cpus=8 cpufreq=1 "
    "fb_hz=120 fb_threads=6 "
    "touch_no_rpmh=1 touch_poll_us=4000 "
    "thermal=2 metal=1 "
    "androidboot.hardware=peridot androidboot.bootdevice=ufs"
)

# Checksums (to be filled after building)
EXPECTED_CHECKSUMS = {
    "uefi.fd": None,           # SHA256 of UEFI payload
    "peridot.dtb": None,       # SHA256 of DTB
    "initrd.img": None,        # SHA256 of initrd
    "Image": None,             # SHA256 of kernel
    "peridot-media.img": None, # SHA256 of FAT media
}

# ─── Logging ──────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("boot-peridot")


# ─── Helpers ──────────────────────────────────────────────────────

def sha256_file(path: Path) -> str:
    """Compute SHA256 of file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_checksum(path: Path, expected: Optional[str]) -> bool:
    """Verify file checksum."""
    if expected is None:
        log.warning(f"No expected checksum for {path.name}, skipping")
        return True
    actual = sha256_file(path)
    if actual.lower() != expected.lower():
        log.error(f"Checksum mismatch for {path.name}: expected {expected}, got {actual}")
        return False
    log.info(f"Checksum OK: {path.name}")
    return True


def run_cmd(cmd: list, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    """Run command with logging."""
    log.debug(f"Running: {' '.join(cmd)}")
    return subprocess.run(cmd, check=check, capture_output=capture, text=True)


def fastboot_boot(uefi_path: Path) -> bool:
    """Boot UEFI via fastboot."""
    log.info(f"Booting UEFI via fastboot: {uefi_path}")
    try:
        run_cmd(["fastboot", "boot", str(uefi_path)])
        return True
    except subprocess.CalledProcessError as e:
        log.error(f"fastboot boot failed: {e}")
        return False


def adb_wait_for_device(timeout: int = 60) -> bool:
    """Wait for ADB device to appear."""
    log.info("Waiting for ADB device...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            result = run_cmd(["adb", "get-state"], check=False, capture=True)
            if result.returncode == 0 and "device" in result.stdout:
                log.info("ADB device ready")
                return True
        except Exception:
            pass
        time.sleep(1)
    log.error("ADB device not ready within timeout")
    return False


def adb_push(local: Path, remote: str) -> bool:
    """Push file via ADB."""
    log.info(f"Pushing {local.name} to {remote}")
    try:
        run_cmd(["adb", "push", str(local), remote])
        return True
    except subprocess.CalledProcessError as e:
        log.error(f"ADB push failed: {e}")
        return False


def adb_shell(cmd: str, timeout: int = 30) -> Tuple[bool, str]:
    """Run command via ADB shell."""
    try:
        result = run_cmd(["adb", "shell", cmd], check=False, capture=True, timeout=timeout)
        return result.returncode == 0, result.stdout.strip()
    except subprocess.TimeoutExpired:
        log.error(f"ADB shell timeout: {cmd}")
        return False, ""


def start_thermal_guard() -> bool:
    """Start thermal guard daemon on device."""
    log.info("Starting thermal guard...")
    # Thermal guard should be started by init in the ramdisk
    # This just verifies it's running
    ok, out = adb_shell("pgrep -f thermal-guard")
    if ok and out:
        log.info(f"Thermal guard running (PID: {out})")
        return True
    log.warning("Thermal guard not detected")
    return False


def verify_touch() -> bool:
    """Verify touchscreen is working."""
    log.info("Verifying touchscreen...")
    ok, out = adb_shell("ls /dev/input/event* | wc -l")
    if ok:
        log.info(f"Input devices: {out}")
    # Check for goodix touch
    ok, out = adb_shell("cat /proc/bus/input/devices | grep -i goodix")
    if ok and out:
        log.info("Goodix touchscreen detected")
        return True
    log.warning("Touchscreen not detected")
    return False


def verify_gpu() -> bool:
    """Verify GPU is working."""
    log.info("Verifying GPU...")
    ok, out = adb_shell("ls /sys/class/drm/")
    if ok:
        log.info(f"DRM devices: {out}")
    ok, out = adb_shell("dmesg | grep -i adreno | tail -5")
    if ok and out:
        log.info(f"Adreno log: {out}")
    return True


def verify_wifi() -> bool:
    """Verify WiFi is working."""
    log.info("Verifying WiFi...")
    ok, out = adb_shell("ls /sys/class/net/ | grep -E 'wlan|wifi'")
    if ok and out:
        log.info(f"WiFi interface: {out}")
        return True
    log.warning("WiFi not detected")
    return False


# ─── Main Boot Flow ───────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Boot Peridot Armada RAM image")
    parser.add_argument("--uefi", required=True, type=Path, help="UEFI payload (fd)")
    parser.add_argument("--media", required=True, type=Path, help="FAT media image")
    parser.add_argument("--dtb", required=True, type=Path, help="Device tree blob")
    parser.add_argument("--initrd", required=True, type=Path, help="Initrd image")
    parser.add_argument("--kernel", required=True, type=Path, help="Kernel Image")
    parser.add_argument("--bootargs", default=DEFAULT_BOOTARGS, help="Kernel boot args")
    parser.add_argument("--skip-checksums", action="store_true", help="Skip checksum verification")
    parser.add_argument("--wait-adb", type=int, default=120, help="ADB wait timeout (seconds)")
    args = parser.parse_args()

    # Verify all input files exist
    files = [args.uefi, args.media, args.dtb, args.initrd, args.kernel]
    for f in files:
        if not f.exists():
            log.error(f"File not found: {f}")
            return 1

    # Verify checksums
    if not args.skip_checksums:
        log.info("Verifying checksums...")
        for f in files:
            if not verify_checksum(f, EXPECTED_CHECKSUMS.get(f.name)):
                return 1

    # Boot UEFI via fastboot
    log.info("=== Booting UEFI ===")
    if not fastboot_boot(args.uefi):
        return 1

    # Wait for UEFI to boot and present USB (fastbootd or ADB)
    log.info("Waiting for UEFI to initialize...")
    time.sleep(5)

    # Push media, DTB, initrd, kernel to device via ADB (or fastboot)
    # The UEFI should have a USB CDC recovery interface for this
    log.info("=== Pushing boot components ===")
    if not adb_wait_for_device(30):
        log.error("ADB not available after UEFI boot")
        return 1

    # Push files to device (UEFI should mount a RAM filesystem or similar)
    # This depends on the UEFI implementation
    for f in [args.media, args.dtb, args.initrd, args.kernel]:
        if not adb_push(f, f"/data/{f.name}"):
            return 1

    # Trigger UEFI to boot Linux with our components
    # This requires UEFI support for: load FDT, load media, chain to Linux
    log.info("=== Triggering Linux boot ===")
    ok, out = adb_shell(f"uefi-boot-linux --kernel /data/Image --initrd /data/initrd.img --dtb /data/peridot.dtb --media /data/peridot-media.img --bootargs '{args.bootargs}'")
    if not ok:
        log.error(f"UEFI boot command failed: {out}")
        return 1

    # Wait for Linux to boot and ADB to reappear
    log.info("Waiting for Linux to boot...")
    if not adb_wait_for_device(args.wait_adb):
        return 1

    # Verify hardware
    log.info("=== Hardware Verification ===")
    start_thermal_guard()
    verify_touch()
    verify_gpu()
    verify_wifi()

    log.info("=== Boot Complete ===")
    log.info("Peridot Armada desktop should now be running!")
    return 0


if __name__ == "__main__":
    sys.exit(main())