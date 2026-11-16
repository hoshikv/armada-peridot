#!/usr/bin/env python3
"""
Thermal Watchdog for Xiaomi Peridot (SM8635)

Independent monitor that reboots the device if the thermal guard
heartbeat stops for more than 12 seconds.

Adapted from armada-dodge thermal-watchdog.py.
"""

import os
import sys
import time
import signal
import logging
from pathlib import Path

HEARTBEAT_PATH = "/run/thermal-guard.heartbeat"
MAX_HEARTBEAT_AGE = 12  # seconds

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/var/log/thermal-watchdog.log"),
    ],
)
log = logging.getLogger("thermal-watchdog")


def emergency_reboot(reason: str):
    """Trigger immediate cold reboot."""
    log.critical(f"EMERGENCY REBOOT: {reason}")
    try:
        # Force kernel panic
        Path("/proc/sys/kernel/panic").write_text("0")
        Path("/proc/sys/kernel/panic_on_oops").write_text("1")
        os.kill(os.getpid(), signal.SIGKILL)
    except Exception:
        pass
    sys.exit(1)


def main():
    if os.geteuid() != 0:
        log.error("Must run as root")
        sys.exit(1)

    log.info("Thermal Watchdog starting for Peridot (SM8635)")
    log.info(f"Monitoring heartbeat at {HEARTBEAT_PATH}, max age {MAX_HEARTBEAT_AGE}s")

    signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
    signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))

    while True:
        try:
            if Path(HEARTBEAT_PATH).exists():
                content = Path(HEARTBEAT_PATH).read_text().strip()
                last_beat = float(content)
                age = time.time() - last_beat
                if age > MAX_HEARTBEAT_AGE:
                    emergency_reboot(f"Thermal guard heartbeat stopped ({age:.1f}s ago)")
            else:
                log.warning("Heartbeat file not found, waiting for thermal guard...")
        except (ValueError, OSError) as e:
            log.warning(f"Heartbeat read error: {e}")

        time.sleep(1)


if __name__ == "__main__":
    main()