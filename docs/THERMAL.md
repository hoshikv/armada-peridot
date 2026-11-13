# Thermal control

The first eight-core test exposed no thermal zones or cpufreq policies. It was returned to Android before further load. The successful build adds four upstream SM8750 TSENS blocks, CPUCP mailbox/shared SRAM, the SCMI performance protocol and CPU performance domains while preserving the existing PSCI domains.

The exact Linux 7.3 kernel already includes the SCMI mailbox/performance/cpufreq and CPU thermal support. Matching stock `qcom_tsens` and `qcom-spmi-temp-alarm` modules are loaded by the guard. The DT recipe uses Armada's CPU cooling-map patch, with lower experimental CPU trips: 70/80°C passive, 90°C hot, 95°C critical. The kernel uses step-wise cooling.

## Startup and supervision

- Boot starts with `maxcpus=1` and the schedutil default governor.
- All 16 CPU and 8 GPU sensor readings must be present and valid.
- CPU0 is capped before the prime policy is brought online. Both SCMI policies, usable cooling devices and every CPU zone's cooling binding must be present before the remaining CPUs/desktop start.
- Normal ceilings are rounded down to supported firmware frequencies: 1,363,200 kHz for CPUs 0–5 and 1,401,600 kHz for CPUs 6–7.
- Readings are sampled every 0.5 seconds. At 70°C, ceilings become 960,000 / 1,017,600 kHz; at 80°C, minimums 384,000 / 1,017,600 kHz. Recovery hysteresis is 65/75°C.
- 85°C on a valid monitored SoC/PMIC reading requests a cold reboot to Android. Missing/invalid required readings, disappearing control policies, failed cap readback or a sustained clock above the requested ceiling also request recovery.
- An independent watchdog requests recovery if the guard's monotonic heartbeat stops for 12 seconds.
- Steam launch paths check that thermal monitoring is healthy. The GPU remains capped at 222 MHz.

Prime CPUs cannot go below 1,017,600 kHz on the tested firmware. Asking for a nominal 1 GHz ceiling must therefore use that firmware minimum rather than fail or request an unsupported value.

## What was verified

On the real device, all eight CPUs, 16 CPU sensors, 8 GPU sensors, two SCMI policies and two cpufreq cooling devices were present. Both policies reported schedutil and clocks within the requested ceilings. Wayland/Adreno compositing, 150% scale and the 120 Hz mode remained active.

The fixed `thermaltest` USB command emulates 75°C on one CPU sensor for six seconds, captures guard/cooling state, and resets `emul_temp` to zero in `finally`. It is restricted to a healthy, cool guard state. The observed ceilings became 960 MHz / 1.0176 GHz and CPU0's kernel cooling state changed from 0 to 1. After resetting emulation, the guard returned to normal and the actual peak CPU reading was 48.6°C.

This tests the software/kernel reaction to synthetic input; it does not physically heat the phone. Eight host tests also cover escalation, hysteresis, invalid/missing CPU readings, supported-frequency rounding and the prime firmware minimum. The 80°C minimum and 85°C recovery branches were not tested by physically reaching those temperatures. Ordinary USB cold reboot to Android was verified separately.

## Limits

Battery, skin and charging thermal management have not been validated. These experimental controls are not equivalent to Android's complete thermal management, and they do not establish a guarantee against overheating or protection during a kernel/firmware lockup. CPU die temperatures are not battery or enclosure temperatures. Older fallback images lack the verified guard. Deep suspend and speaker audio remain deferred.
