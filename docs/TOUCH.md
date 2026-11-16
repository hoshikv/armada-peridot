# Touchscreen Support for Peridot (SM8635)

Adapted from armada-dodge touch documentation for OnePlus 13 (S3910) and xnu-kernel-peridot Goodix driver.

## Hardware Specifications

| Property | Value |
|----------|-------|
| Controller | Goodix GT9916R (Berlin-D) |
| Interface | SPI via QUPv3 SE4 |
| Max Touch Points | 10 |
| Resolution | 19520 × 43400 (raw) → 1220 × 2712 (display) |
| Report Rate | 240 Hz (480 Hz with `touch_rate=480`) |
| Poll Interval | 8000 µs default (configurable via `touch_poll_us`) |

## Pin Mapping (from xnu-kernel-peridot)

| Signal | GPIO | Function |
|--------|------|----------|
| MISO | 16 | SPI Data In |
| MOSI | 17 | SPI Data Out |
| CLK | 18 | SPI Clock |
| CS | 19 | SPI Chip Select |
| INT | 129 | Interrupt (active low) |
| RESET | 128 | Reset (active low) |

## Power Supply

| Rail | Regulator | Voltage | Source |
|------|-----------|---------|--------|
| VDD_1V8 | LDOB23 | 1.8V | PMIC via RPMh |
| VDD_3V3 | LDOB13 | 3.3V | PMIC via RPMh |

## QUPv3 SPI Controller

- **Base Address**: `0x00A90000` (QUPv3_1_GENI_SE)
- **Clock**: GCC_QUPV3_1_GENI_SE_CLK @ `0x73000`
- **IRQ**: GIC_SPI 200
- **Max Frequency**: 4 MHz

## Driver

See `source/linux/drivers/input/touchscreen/goodix_peridot.c` for the kernel driver.

### Key Features
- SPI communication (not I2C like older Goodix)
- Firmware loading via request_firmware()
- Configuration loading
- Multi-touch (10 points) via MT protocol
- Interrupt-driven (falling edge on INT pin)
- Power management (suspend/resume)
- Gesture support (TODO)

### Firmware Files Required
Place in `/lib/firmware/`:
- `goodix_gt9916r_peridot.fw` - Firmware binary
- `goodix_gt9916r_peridot.cfg` - Configuration data

## Device Tree

See `experimental/peridot-touch-v1/sm8635-touch.dtsi` for complete touch DT.

### Key Nodes
- `qupv3_1_geni_se` - QUPv3 SPI controller
- `goodix_ts` - Touch controller device
- TLMM pinmux for SPI GPIOs (16-19)
- TLMM for RESET (GPIO 128) and INT (GPIO 129)
- RPMh regulators for LDOB23 and LDOB13

## Boot Arguments

```
touch_no_rpmh=1    # Skip RPMh power control (use direct GPIO)
touch_poll_us=4000 # Poll interval in microseconds
touch_rate=480     # Report rate (240 or 480 Hz)
```

## Integration with Armada-Dodge

### UEFI Touch Lease
The UEFI must:
1. Initialize touch controller (power, reset, firmware)
2. Lease touch firmware to Linux (pass via FDT or shared memory)
3. Disable kernel SPI node for QUPv3 SE4 (so userspace driver can bind)

### Userspace Driver (Alternative)
Like armada-dodge's `op13-touch.c`, a userspace driver can:
- Bitbang SPI via GPIO (if kernel SPI unavailable)
- Feed uinput events directly
- Useful for early boot / recovery

## Kernel Config

```kconfig
CONFIG_INPUT_TOUCHSCREEN=y
CONFIG_TOUCHSCREEN_GOODIX=m
CONFIG_TOUCHSCREEN_GOODIX_SPI=y
CONFIG_SPI_QUP_V3=y
CONFIG_PINCTRL_QCOM=y
CONFIG_REGULATOR_QCOM_RPMH=y
```

## Debugging

### Check Touch Input
```bash
# Input device
ls /dev/input/event*
cat /proc/bus/input/devices

# Test touch
evtest /dev/input/eventX
```

### Kernel Logs
```bash
dmesg | grep -i goodix
dmesg | grep -i touch
```

### SPI Communication
```bash
# SPI debugfs
ls /sys/kernel/debug/spi_master/
cat /sys/kernel/debug/spi_master/spi*/statistics
```

### GPIO Status
```bash
cat /sys/kernel/debug/gpio | grep -E "128|129|16|17|18|19"
```

### Regulator Status
```bash
cat /sys/class/regulator/ldob23/state
cat /sys/class/regulator/ldob13/state
```

## Known Issues / TODO

- [ ] Obtain actual Goodix GT9916R firmware and config for Peridot
- [ ] Verify SPI mode (0 vs 3) and timing
- [ ] Implement gesture recognition (double tap, swipe)
- [ ] Add touch firmware version reporting
- [ ] Test with actual hardware for coordinate calibration
- [ ] Implement userspace fallback driver (like armada-dodge op13-touch)
- [ ] Verify RPMh regulator IDs for LDOB23/LDOB13
- [ ] Add support for `touch_no_rpmh` boot arg
- [ ] Test interrupt polarity (active low vs high)