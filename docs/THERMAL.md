# Thermal Management for Peridot (SM8635)

Adapted from armada-dodge thermal documentation for OnePlus 13 (SM8750).

## Hardware Overview

### TSENS Blocks (3 total, 27 sensors each = 81 zones)

| Block | Base Address | Sensors | Primary Coverage |
|-------|--------------|---------|------------------|
| TSENS0 | `0x0C222000` | 0-26 | CPU Cluster 0 (small), Cluster 1 (big), Battery |
| TSENS1 | `0x0C223000` | 0-26 | CPU Cluster 1 (big), Cluster 2 (prime), GPU |
| TSENS2 | `0x0C224000` | 0-26 | CPU Cluster 2 (prime), GPU, Skin/Ambient |

### Sensor Register Format

- **Offset**: `0xA0 + 4 × sensor_index`
- **Bits 0-11**: 12-bit temperature reading (tenths of °C)
- **Bit 21**: Valid flag (1 = reading valid)
- **Formula**: `temp_°C = (raw & 0xFFF) / 10.0`

### CPU Topology & Thermal Mapping

```
Cluster 0 (Small): CPU0, CPU1, CPU2  → Cortex-A520  → SCMI Domain 0 → TSENS0 sensors 0-2
Cluster 1 (Big):   CPU3, CPU4, CPU5, CPU6 → Cortex-A720 → SCMI Domain 1 → TSENS0 sensors 3-6
Cluster 2 (Prime): CPU7                  → Cortex-X4   → SCMI Domain 2 → TSENS1 sensor 0
```

### GPU Thermal

- Adreno 735 monitored via TSENS1 sensor 1 (and TSENS2)
- GMU firmware reports thermal status via SCMI
- Cooling via GMU frequency scaling

### Battery Thermal

- Monitored via TSENS0 sensors 7-9 (typically)
- Two-tier response:
  - 50°C: Request half speed on all clusters
  - 58°C: Request lowest speed on all clusters

## Thermal Limits

| Limit | Temperature | Action |
|-------|-------------|--------|
| Core Passive | 95°C | SCMI DVFS throttling |
| Other Sensors | 100°C | Aggressive throttling |
| Emergency | 115°C | Cold reboot (kernel panic) |
| Battery Half | 50°C | All clusters → half max freq |
| Battery Lowest | 58°C | All clusters → min freq |

## Cooling Trip Points

| Trip | Temperature | Cooling Level |
|------|-------------|---------------|
| 0 | 70°C | Light (level 10) |
| 1 | 80°C | Moderate (level 8) |
| 2 | 85°C | Heavy (level 7) |
| 3 | 90°C | Severe (level 5) |
| 4 | 95°C | Critical (level 0 = min freq) |

## SCMI DVFS Implementation

### SM8635 Differences from SM8750

| Aspect | SM8750 (OnePlus 13) | SM8635 (Peridot) |
|--------|---------------------|------------------|
| CPU Clusters | 2 (Oryon) | 3 (A520/A720/X4) |
| SCMI Domains | 2 | 3 |
| APPS RSC | Different address | `0x17A20000` |
| CPUSYS SRAM | Different address | `0x14600000` |

### SCMI Performance Protocol

- Protocol ID: `0x12`
- Each cluster = 1 performance domain
- Domain 0: Cluster 0 (small, 3 CPUs)
- Domain 1: Cluster 1 (big, 4 CPUs)
- Domain 2: Cluster 2 (prime, 1 CPU)

### Mailbox Communication

```
APPS RSC (0x17A20000) → RPMh → SCMI Mailbox in CPUSYS SRAM (0x14600000)
```

The `qcom-scmi` kernel driver handles the mailbox protocol. Userspace thermal guard uses sysfs interface at `/sys/bus/platform/drivers/qcom-scmi/perf_domain_*`.

## Thermal Guard Daemon

### Components

1. **thermal-guard.py** - Main daemon:
   - Polls all 81 sensors every 250ms
   - Validates sensor coverage (>80% reporting)
   - Applies per-cluster cooling via SCMI
   - Monitors battery/skin thermals
   - Detects sensor failures
   - Writes heartbeat for watchdog

2. **thermal-watchdog.py** - Independent monitor:
   - Checks thermal-guard heartbeat every 1s
   - Triggers cold reboot if heartbeat >12s old
   - Runs as separate process for redundancy

### Sysfs Interface Used

```
/sys/class/thermal/thermal_zone*/temp     # Sensor readings
/sys/devices/system/cpu/cpu*/cpufreq/     # CPU frequency control
/sys/bus/platform/drivers/qcom-scmi/perf_domain_*/level  # SCMI perf levels
```

## Device Tree Requirements

The thermal DT (`sm8635-thermal.dtsi`) must define:

1. **TSENS nodes** with correct base addresses and sensor counts
2. **Thermal zones** for each CPU, GPU, battery, skin
3. **Cooling maps** linking trips to SCMI cooling devices
4. **SCMI mailbox** in CPUSYS SRAM
5. **Reserved memory** for SMEM/SCMI shared memory

## Integration with Armada Userspace

The thermal guard runs in the Arch Linux ARM userspace (host initrd), not in the Armada container. It requires:

- Root privileges
- Access to kernel headers matching running kernel (for module builds)
- `qcom_tsens` and `qcom-spmi-temp-alarm` kernel modules loaded
- SCMI mailbox functional (UEFI must initialize APPS RSC)

## Boot-Time Requirements

UEFI must:
1. Initialize APPS RSC at `0x17A20000`
2. Configure CPUSYS SRAM at `0x14600000` for SCMI mailbox
3. Populate FDT with thermal zones and SCMI nodes
4. Lease touch firmware (separate but concurrent)
5. Start USB CDC recovery interface

## Debugging

### Check Sensor Readings
```bash
# All thermal zones
cat /sys/class/thermal/thermal_zone*/temp

# Specific sensor via debugfs
cat /sys/kernel/debug/qcom_tsens/tsens0/sensor0
```

### Check SCMI Domains
```bash
ls /sys/bus/platform/drivers/qcom-scmi/
cat /sys/bus/platform/drivers/qcom-scmi/perf_domain_0/level
```

### Verify Cooling Maps
```bash
cat /sys/class/thermal/thermal_zone*/trip_point_*_temp
cat /sys/class/thermal/cooling_device*/cur_state
```

### Logs
```bash
tail -f /var/log/thermal-guard.log
tail -f /var/log/thermal-watchdog.log
```

## Known Issues / TODO

- [ ] Calibrate sensor-to-cluster mapping (currently heuristic)
- [ ] Add GPU cooling via GMU SCMI (separate from CPU)
- [ ] Implement skin thermal sensor identification
- [ ] Add charging thermal monitoring (PMIC)
- [ ] Test with actual hardware thermal loads
- [ ] Tune trip points for Peridot's thermal solution