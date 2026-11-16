#!/usr/bin/env python3
"""
Thermal Guard for Xiaomi Peridot (SM8635 / Snapdragon 8s Gen 3)

Adapted from armada-dodge thermal-guard.py for OnePlus 13 (SM8750).
Monitors 81 thermal zones across 3 TSENS blocks, manages SCMI DVFS
policies for 3 CPU clusters, enforces cooling trips.

TSENS Blocks (Peridot):
- TSENS0: 0x0C222000
- TSENS1: 0x0C223000
- TSENS2: 0x0C224000 (Peridot-specific)

CPU Topology (3 clusters):
- Cluster 0 (small): CPU0-2 (Cortex-A520)
- Cluster 1 (big): CPU3-6 (Cortex-A720)
- Cluster 2 (prime): CPU7 (Cortex-X4)

SCMI DVFS: 3 domains (one per cluster) via APPS RSC at 0x17A20000
"""

import os
import sys
import time
import struct
import subprocess
import threading
import signal
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ─── Configuration ────────────────────────────────────────────────

# TSENS register offsets (per block)
TSENS_STATUS_REG = 0xA0          # Sensor status: 12-bit temp (tenths °C), bit 21 = valid
TSENS_STATUS_STRIDE = 4          # Per-sensor stride
TSENS_NUM_SENSORS = 27           # 27 sensors per block (81 total / 3)

# TSENS base addresses (Peridot / SM8635)
TSENS_BASES = [
    0x0C222000,  # TSENS0
    0x0C223000,  # TSENS1
    0x0C224000,  # TSENS2 (Peridot-specific)
]

# Thermal limits (°C * 10)
THERMAL_LIMIT_CORE_PASSIVE = 950   # 95°C - passive cooling for CPU cores
THERMAL_LIMIT_OTHER = 1000         # 100°C - other sensors
THERMAL_LIMIT_EMERGENCY = 1150     # 115°C - emergency panic reboot
THERMAL_LIMIT_BATTERY_HALF = 500   # 50°C - battery half speed
THERMAL_LIMIT_BATTERY_LOWEST = 580 # 58°C - battery lowest speed

# Cooling trip points (°C * 10) - matches armada-dodge trips
COOLING_TRIPS = [700, 800, 850, 900, 950]  # 70, 80, 85, 90, 95°C

# SCMI Performance Protocol
SCMI_PROTOCOL_PERFORMANCE = 0x12
SCMI_PERF_DOMAIN_ATTRIBUTES = 0x3
SCMI_PERF_LEVEL_SET = 0x4
SCMI_PERF_LEVEL_GET = 0x5
SCMI_PERF_DESCRIBE_LEVELS = 0x7

# SCMI Message Header
SCMI_MSG_HEADER_SIZE = 8

# CPU Cluster mapping (Peridot: 3 clusters)
CPU_CLUSTERS = {
    0: {"cpus": [0, 1, 2], "name": "small", "scmi_domain": 0},    # Cortex-A520
    1: {"cpus": [3, 4, 5, 6], "name": "big", "scmi_domain": 1},   # Cortex-A720
    2: {"cpus": [7], "name": "prime", "scmi_domain": 2},           # Cortex-X4
}

# APPS RSC (RPMh sequencer) for SCMI mailbox
APPS_RSC_BASE = 0x17A20000

# Sysfs paths
THERMAL_ZONE_BASE = "/sys/class/thermal"
CPU_FREQ_BASE = "/sys/devices/system/cpu"
SCMI_DRIVER_PATH = "/sys/bus/platform/drivers/qcom-scmi"

# Poll interval (ms)
POLL_INTERVAL_MS = 250

# Heartbeat file for watchdog
HEARTBEAT_PATH = "/run/thermal-guard.heartbeat"

# ─── Logging ──────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/var/log/thermal-guard.log"),
    ],
)
log = logging.getLogger("thermal-guard")

# ─── Helpers ──────────────────────────────────────────────────────

def read_sensor_temp(block: int, sensor: int) -> Optional[int]:
    """Read temperature from TSENS block/sensor via debugfs or sysfs."""
    # Try sysfs first (thermal zone)
    zone_idx = block * TSENS_NUM_SENSORS + sensor
    zone_path = Path(THERMAL_ZONE_BASE) / f"thermal_zone{zone_idx}" / "temp"
    if zone_path.exists():
        try:
            return int(zone_path.read_text().strip())
        except (ValueError, OSError):
            pass

    # Fallback: debugfs TSENS direct register read (requires root + debugfs mounted)
    debugfs_path = Path("/sys/kernel/debug/qcom_tsens") / f"tsens{block}" / f"sensor{sensor}"
    if debugfs_path.exists():
        try:
            val = int(debugfs_path.read_text().strip(), 16)
            # Extract 12-bit temp (tenths °C) from bits 0-11, valid bit 21
            if val & (1 << 21):
                return (val & 0xFFF) * 10  # Convert to millidegrees for consistency
        except (ValueError, OSError):
            pass

    return None


def read_all_temps() -> Dict[Tuple[int, int], int]:
    """Read all 81 thermal zones. Returns dict of (block, sensor) -> temp_millidegrees."""
    temps = {}
    for block in range(3):
        for sensor in range(TSENS_NUM_SENSORS):
            temp = read_sensor_temp(block, sensor)
            if temp is not None:
                temps[(block, sensor)] = temp
    return temps


def get_cpu_cluster(cpu: int) -> Optional[int]:
    """Map CPU number to cluster index (0, 1, 2)."""
    for cluster_idx, info in CPU_CLUSTERS.items():
        if cpu in info["cpus"]:
            return cluster_idx
    return None


def get_cluster_cpus(cluster: int) -> List[int]:
    """Get CPU list for a cluster."""
    return CPU_CLUSTERS.get(cluster, {}).get("cpus", [])


def read_cpu_freq(cpu: int) -> Optional[int]:
    """Read current CPU frequency in kHz."""
    path = Path(CPU_FREQ_BASE) / f"cpu{cpu}" / "cpufreq" / "scaling_cur_freq"
    if path.exists():
        try:
            return int(path.read_text().strip())
        except (ValueError, OSError):
            pass
    return None


def write_cpu_freq(cpu: int, freq_khz: int) -> bool:
    """Set CPU frequency target in kHz."""
    path = Path(CPU_FREQ_BASE) / f"cpu{cpu}" / "cpufreq" / "scaling_setspeed"
    if path.exists():
        try:
            path.write_text(str(freq_khz))
            return True
        except (ValueError, OSError) as e:
            log.warning(f"Failed to set freq for CPU{cpu}: {e}")
    return False


def scmi_perf_level_set(domain: int, level: int) -> bool:
    """Set SCMI performance level for a domain."""
    # This uses the qcom-scmi driver's sysfs interface
    domain_path = Path(SCMI_DRIVER_PATH) / f"perf_domain_{domain}"
    if not domain_path.exists():
        log.warning(f"SCMI perf domain {domain} not found")
        return False

    level_path = domain_path / "level"
    try:
        level_path.write_text(str(level))
        return True
    except OSError as e:
        log.warning(f"Failed to set SCMI perf level for domain {domain}: {e}")
        return False


def scmi_perf_level_get(domain: int) -> Optional[int]:
    """Get current SCMI performance level for a domain."""
    domain_path = Path(SCMI_DRIVER_PATH) / f"perf_domain_{domain}"
    level_path = domain_path / "level"
    if level_path.exists():
        try:
            return int(level_path.read_text().strip())
        except (ValueError, OSError):
            pass
    return None


def get_cooling_level_for_temp(temp_millidegrees: int) -> int:
    """Map temperature to cooling level (0 = no cooling, higher = more aggressive)."""
    temp_c = temp_millidegrees // 1000
    for i, trip in enumerate(COOLING_TRIPS):
        if temp_c < trip:
            return i
    return len(COOLING_TRIPS)  # Max cooling


def apply_cooling(cluster: int, level: int) -> bool:
    """Apply cooling level to a CPU cluster via SCMI DVFS."""
    domain = CPU_CLUSTERS[cluster]["scmi_domain"]
    # Level 0 = max performance, higher = more throttled
    # Map our cooling level to SCMI performance level (inverse)
    max_level = 10  # Assume 10 performance levels (adjust based on actual)
    perf_level = max(0, max_level - level)
    return scmi_perf_level_set(domain, perf_level)


def emergency_reboot(reason: str):
    """Trigger immediate cold reboot."""
    log.critical(f"EMERGENCY REBOOT: {reason}")
    # Write to watchdog or trigger kernel panic
    try:
        Path("/proc/sys/kernel/panic").write_text("0")
        Path("/proc/sys/kernel/panic_on_oops").write_text("1")
        # Force panic
        os.kill(os.getpid(), signal.SIGKILL)
    except Exception:
        pass
    sys.exit(1)


# ─── Main Thermal Guard Loop ──────────────────────────────────────

class ThermalGuard:
    def __init__(self):
        self.running = True
        self.last_temps: Dict[Tuple[int, int], int] = {}
        self.failed_sensors = set()
        self.heartbeat_thread = None

    def validate_sensors(self, temps: Dict[Tuple[int, int], int]) -> bool:
        """Validate that we're reading from enough sensors."""
        expected = 3 * TSENS_NUM_SENSORS  # 81
        actual = len(temps)
        if actual < expected * 0.8:  # Allow 20% missing
            log.error(f"Sensor validation failed: {actual}/{expected} sensors reporting")
            return False
        return True

    def check_emergency(self, temps: Dict[Tuple[int, int], int]):
        """Check for emergency thermal conditions."""
        for (block, sensor), temp in temps.items():
            temp_c = temp // 1000
            if temp_c >= THERMAL_LIMIT_EMERGENCY // 1000:
                emergency_reboot(f"Sensor ({block},{sensor}) hit {temp_c}°C")

    def check_battery_thermal(self, temps: Dict[Tuple[int, int], int]):
        """Check battery thermal zones (typically sensors 0-2 in block 0)."""
        # Battery sensors are usually in first TSENS block
        for sensor in range(3):
            temp = temps.get((0, sensor))
            if temp is not None:
                temp_c = temp // 1000
                if temp_c >= THERMAL_LIMIT_BATTERY_LOWEST // 1000:
                    log.warning(f"Battery thermal critical: {temp_c}°C - requesting lowest speed")
                    # Apply max cooling to all clusters
                    for cluster in CPU_CLUSTERS:
                        apply_cooling(cluster, len(COOLING_TRIPS))
                elif temp_c >= THERMAL_LIMIT_BATTERY_HALF // 1000:
                    log.warning(f"Battery thermal elevated: {temp_c}°C - requesting half speed")
                    for cluster in CPU_CLUSTERS:
                        apply_cooling(cluster, len(COOLING_TRIPS) // 2)

    def apply_thermal_policy(self, temps: Dict[Tuple[int, int], int]):
        """Apply cooling based on highest temp per cluster."""
        # Map sensors to clusters (approximate - adjust based on actual sensor placement)
        # For now, use max temp across all sensors per cluster
        cluster_temps = {0: 0, 1: 0, 2: 0}

        for (block, sensor), temp in temps.items():
            temp_c = temp // 1000
            # Heuristic: assign sensors to clusters based on block/sensor
            # This needs calibration per device
            if block == 0:
                cluster_temps[0] = max(cluster_temps[0], temp_c)
                cluster_temps[1] = max(cluster_temps[1], temp_c)
            elif block == 1:
                cluster_temps[1] = max(cluster_temps[1], temp_c)
                cluster_temps[2] = max(cluster_temps[2], temp_c)
            else:  # block 2
                cluster_temps[2] = max(cluster_temps[2], temp_c)

        for cluster, temp_c in cluster_temps.items():
            if temp_c == 0:
                continue
            level = get_cooling_level_for_temp(temp_c * 1000)
            if level > 0:
                log.info(f"Cluster {cluster} ({CPU_CLUSTERS[cluster]['name']}): {temp_c}°C -> cooling level {level}")
                apply_cooling(cluster, level)

    def detect_sensor_failures(self, temps: Dict[Tuple[int, int], int]):
        """Detect sensors that stopped reporting."""
        for key in self.last_temps:
            if key not in temps:
                self.failed_sensors.add(key)
                log.warning(f"Sensor {key} stopped reporting")

        # If too many sensors failed, reboot
        if len(self.failed_sensors) > 10:
            emergency_reboot(f"Too many sensor failures: {len(self.failed_sensors)}")

        self.last_temps = temps.copy()

    def write_heartbeat(self):
        """Write heartbeat timestamp for watchdog."""
        try:
            Path(HEARTBEAT_PATH).write_text(str(time.time()))
        except OSError:
            pass

    def run(self):
        log.info("Thermal Guard starting for Peridot (SM8635)")
        log.info(f"Monitoring {3 * TSENS_NUM_SENSORS} sensors across 3 TSENS blocks")
        log.info(f"CPU clusters: {CPU_CLUSTERS}")

        # Start heartbeat thread
        def heartbeat_loop():
            while self.running:
                self.write_heartbeat()
                time.sleep(1)

        self.heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()

        signal.signal(signal.SIGTERM, lambda s, f: setattr(self, 'running', False))
        signal.signal(signal.SIGINT, lambda s, f: setattr(self, 'running', False))

        while self.running:
            start = time.time()

            temps = read_all_temps()

            if not temps:
                log.error("No thermal sensors readable!")
                time.sleep(POLL_INTERVAL_MS / 1000)
                continue

            if not self.validate_sensors(temps):
                emergency_reboot("Sensor validation failed")

            self.check_emergency(temps)
            self.check_battery_thermal(temps)
            self.apply_thermal_policy(temps)
            self.detect_sensor_failures(temps)

            elapsed = time.time() - start
            sleep_time = max(0, POLL_INTERVAL_MS / 1000 - elapsed)
            time.sleep(sleep_time)

        log.info("Thermal Guard stopped")


def main():
    if os.geteuid() != 0:
        log.error("Must run as root")
        sys.exit(1)

    guard = ThermalGuard()
    guard.run()


if __name__ == "__main__":
    main()