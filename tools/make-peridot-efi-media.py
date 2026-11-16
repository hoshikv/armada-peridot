#!/usr/bin/env python3
"""
FAT Media Image Builder for Xiaomi Peridot Armada RAM Boot

Adapted from armada-dodge make-op13-efi-media.py.
Creates a FAT32 image containing:
- Kernel (Image)
- Initrd
- DTB
- Kernel modules
- Firmware
- Armada userspace (OCI extracted)
- Arch Linux ARM userspace
- Steam client overlay
"""

import os
import sys
import argparse
import subprocess
import tempfile
import shutil
import logging
from pathlib import Path
from typing import List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("make-media")


# ─── Configuration ────────────────────────────────────────────────

MEDIA_SIZE_MB = 2048  # 2GB FAT32 image
FAT_LABEL = "PERIDOT"
SECTOR_SIZE = 512

# Directory structure in FAT media
MEDIA_DIRS = [
    "boot",           # Kernel, initrd, DTB
    "modules",        # Kernel modules (.ko)
    "firmware",       # Firmware files
    "armada",         # Armada userspace root
    "arch",           # Arch Linux ARM userspace
    "steam",          # Steam client overlay
    "thermal",        # Thermal guard scripts
]


# ─── Helpers ──────────────────────────────────────────────────────

def run_cmd(cmd: list, check: bool = True, cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    """Run command with logging."""
    log.debug(f"Running: {' '.join(cmd)}")
    return subprocess.run(cmd, check=check, cwd=cwd, capture_output=True, text=True)


def copy_tree(src: Path, dst: Path, exclude: Optional[List[str]] = None):
    """Copy directory tree with optional exclusions."""
    exclude = exclude or []
    for item in src.rglob("*"):
        rel = item.relative_to(src)
        if any(rel.match(pat) for pat in exclude):
            continue
        target = dst / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def create_fat_image(output: Path, size_mb: int, label: str, source_dir: Path) -> bool:
    """Create FAT32 image from directory."""
    log.info(f"Creating {size_mb}MB FAT32 image: {output}")

    # Create empty image
    sectors = (size_mb * 1024 * 1024) // SECTOR_SIZE
    run_cmd(["dd", "if=/dev/zero", f"of={output}", f"bs={SECTOR_SIZE}", f"count={sectors}"])

    # Format as FAT32
    run_cmd(["mkfs.vfat", "-F", "32", "-n", label, str(output)])

    # Mount and copy files
    with tempfile.TemporaryDirectory() as mount_point:
        run_cmd(["sudo", "mount", "-o", "loop,uid=1000,gid=1000", str(output), mount_point])

        try:
            # Copy all files
            for item in source_dir.iterdir():
                if item.is_dir():
                    shutil.copytree(item, Path(mount_point) / item.name, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, Path(mount_point) / item.name)

            # Sync
            run_cmd(["sync"])

        finally:
            run_cmd(["sudo", "umount", mount_point])

    log.info(f"FAT image created: {output}")
    return True


# ─── Main ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Build Peridot Armada FAT media image")
    parser.add_argument("--armada-root", required=True, type=Path, help="Armada OS userspace root")
    parser.add_argument("--arch-root", required=True, type=Path, help="Arch Linux ARM userspace root")
    parser.add_argument("--steam-extra", required=True, type=Path, help="Steam overlay files")
    parser.add_argument("--modules-dir", required=True, type=Path, help="Built kernel modules directory")
    parser.add_argument("--firmware-dir", required=True, type=Path, help="Firmware directory")
    parser.add_argument("--dtb", required=True, type=Path, help="Device tree blob")
    parser.add_argument("--initrd", required=True, type=Path, help="Initrd image")
    parser.add_argument("--kernel", required=True, type=Path, help="Kernel Image")
    parser.add_argument("--output", required=True, type=Path, help="Output FAT image")
    parser.add_argument("--size-mb", type=int, default=MEDIA_SIZE_MB, help="Image size in MB")
    args = parser.parse_args()

    # Verify inputs
    for name, path in [
        ("Armada root", args.armada_root),
        ("Arch root", args.arch_root),
        ("Steam extra", args.steam_extra),
        ("Modules dir", args.modules_dir),
        ("Firmware dir", args.firmware_dir),
    ]:
        if not path.exists():
            log.error(f"{name} not found: {path}")
            return 1

    for name, path in [
        ("DTB", args.dtb),
        ("Initrd", args.initrd),
        ("Kernel", args.kernel),
    ]:
        if not path.exists():
            log.error(f"{name} not found: {path}")
            return 1

    # Create temporary staging directory
    with tempfile.TemporaryDirectory() as staging:
        stage = Path(staging)
        log.info(f"Staging in {stage}")

        # Create directory structure
        for d in MEDIA_DIRS:
            (stage / d).mkdir(parents=True, exist_ok=True)

        # Copy boot files
        log.info("Copying boot files...")
        shutil.copy2(args.kernel, stage / "boot" / "Image")
        shutil.copy2(args.initrd, stage / "boot" / "initrd.img")
        shutil.copy2(args.dtb, stage / "boot" / "peridot.dtb")

        # Copy kernel modules
        log.info("Copying kernel modules...")
        copy_tree(args.modules_dir, stage / "modules")

        # Copy firmware
        log.info("Copying firmware...")
        copy_tree(args.firmware_dir, stage / "firmware")

        # Copy Armada userspace
        log.info("Copying Armada userspace...")
        copy_tree(args.armada_root, stage / "armada", exclude=["*.log", "*.cache", "__pycache__"])

        # Copy Arch userspace
        log.info("Copying Arch userspace...")
        copy_tree(args.arch_root, stage / "arch", exclude=["*.log", "*.cache", "__pycache__", "var/cache", "var/log"])

        # Copy Steam overlay
        log.info("Copying Steam overlay...")
        copy_tree(args.steam_extra, stage / "steam")

        # Copy thermal guard scripts
        log.info("Copying thermal scripts...")
        thermal_src = Path(__file__).parent.parent / "experimental" / "peridot-thermal-v1"
        if thermal_src.exists():
            copy_tree(thermal_src, stage / "thermal")

        # Create boot config
        boot_config = stage / "boot" / "boot.conf"
        boot_config.write_text(f"""# Peridot Armada Boot Configuration
KERNEL=Image
INITRD=initrd.img
DTB=peridot.dtb
BOOTARGS=console=ttyMSM0,115200n8 earlycon=msm_geni_serial,0x888000 bootcpu=7 cpus=8 cpufreq=1 fb_hz=120 fb_threads=6 touch_no_rpmh=1 touch_poll_us=4000 thermal=2 metal=1
""")

        # Create thermal guard service file
        thermal_service = stage / "thermal" / "thermal-guard.service"
        thermal_service.write_text("""[Unit]
Description=Thermal Guard Daemon
After=multi-user.target

[Service]
Type=simple
ExecStart=/thermal/thermal-guard.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
""")

        thermal_watchdog_service = stage / "thermal" / "thermal-watchdog.service"
        thermal_watchdog_service.write_text("""[Unit]
Description=Thermal Watchdog
After=thermal-guard.service

[Service]
Type=simple
ExecStart=/thermal/thermal-watchdog.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
""")

        # Calculate size
        total_size = sum(f.stat().st_size for f in stage.rglob("*") if f.is_file())
        log.info(f"Total staged size: {total_size / (1024*1024):.1f} MB")

        if total_size > args.size_mb * 1024 * 1024 * 0.9:
            log.warning("Staged content exceeds 90% of image size!")

        # Create FAT image
        create_fat_image(args.output, args.size_mb, FAT_LABEL, stage)

    log.info("Media image build complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())