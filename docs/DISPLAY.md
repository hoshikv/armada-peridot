# Display Support for Peridot (SM8635)

Adapted from armada-dodge display documentation for OnePlus 13 (SM8750).

## Hardware Specifications

| Property | Value |
|----------|-------|
| Resolution | 1220 × 2712 |
| Refresh Rate | 120 Hz |
| Interface | MIPI DSI 4-lane |
| Color Depth | 10-bit RGB (10 bpc) |
| Compression | DSC (Display Stream Compression) |
| DSI Mode | Video mode, sync pulse |
| Panel Type | OLED (likely Samsung E6 or BOE) |
| Size | ~6.67" diagonal |

## Display Controller (DPU)

SM8635 uses the DPU (Display Processing Unit) with DSI controller:

| Block | Base Address | Size | Description |
|-------|--------------|------|-------------|
| DPU Core | `0x0AE00000` | `0x30000` | Display Processing Unit |
| INTF (DSI) | `0x0AE36000` | `0x10000` | DSI Interface |
| DISPCC | `0x0AF00000` | `0x10000` | Display Clock Controller |

## DSI PHY

- 4 data lanes + 1 clock lane
- D-PHY mode
- 1.5 Gbps per lane (HS mode)
- 10 Mbps (LP mode)

## Panel Driver

See `source/modules/display/panel-peridot-dsc.c` for the panel driver.

### Key Features
- DSC with 2 slices, slice height 8
- 10 bpc, 128 bits per pixel (compressed)
- Video mode with sync pulse timing
- 4-lane DSI

### Panel Commands
**TODO**: The exact panel initialization sequence needs to be obtained from:
1. Xiaomi kernel source for peridot
2. Panel datasheet (once model is identified)
3. Dumping commands from Android boot

The current driver has placeholder commands. The actual sequence typically includes:
- Command page unlock (0xFF)
- Power control settings
- Display timing configuration
- Gamma/correction settings
- DSC configuration
- Panel-specific registers

## Device Tree

See `experimental/peridot-display-v1/sm8635-display.dtsi` for complete display DT.

### Key Nodes
- `dispcc` - Display clock controller
- `dpu` - DPU with DSI host
- `dsi0` - DSI controller with PHY
- `panel` - Panel device with DSC config
- Power domains (GDSC) for display
- PMIC regulators via SPMI
- GPIO for panel reset

## Kernel Config

```kconfig
CONFIG_DRM_MSM=y
CONFIG_DRM_MSM_DPU=y
CONFIG_DRM_MSM_DSI=y
CONFIG_DRM_MSM_DSI_DSC=y
CONFIG_DRM_PANEL_ORIENTATION_QUIRKS=y
CONFIG_DRM_PANEL=y
CONFIG_DRM_PANEL_XIAOMI_PERIDOT=y  # Our panel driver
CONFIG_VIDEO_MIPI_DSI=y
CONFIG_DRM_DSC=y
```

## Userspace Integration

### Framebuffer
- UEFI GOP framebuffer at `0xE3940000` (from xnu-kernel-peridot)
- Resolution: 1220 × 2712 @ 120 Hz
- Format: RGB888 (24-bit) or XRGB8888 (32-bit)

### Wayland / KWin
- DRM/KMS via MSM driver
- Atomic modesetting
- DSC enabled in kernel
- 150% scaling (as in armada-dodge)

### Boot Arguments
```
fb_hz=120
fb_threads=6
```

## Debugging

### Check Display Status
```bash
# Kernel log
dmesg | grep -i -e dpu -e dsi -e panel -e dispcc

# DRM devices
ls /sys/class/drm/
cat /sys/class/drm/card0/modes

# DPU debugfs
ls /sys/kernel/debug/dri/0/
cat /sys/kernel/debug/dri/0/dpu_debug
```

### Panel Communication
```bash
# DSI trace (if enabled)
echo 1 > /sys/kernel/debug/tracing/events/mipi_dsi/enable

# Panel regs (if panel supports readback)
# Requires panel-specific read commands
```

### Common Issues
1. **No display**: Check DSI PHY training, lane mapping, clock rates
2. **Flickering**: Timing mismatch, DSC configuration error
3. **Wrong colors**: Gamma/color space mismatch, RGB vs BGR lane swap
4. **Partial image**: DSC slice configuration, slice height mismatch

## Known Issues / TODO

- [ ] Identify exact panel model (Samsung S6E3FC3? BOE? CSOT?)
- [ ] Obtain complete panel initialization sequence
- [ ] Verify DSC PPS parameters match panel capabilities
- [ ] Test HDR support (if panel supports)
- [ ] Implement panel self-refresh (PSR) for power saving
- [ ] Add brightness control via DCS or PWM
- [ ] Verify DSI PHY timing parameters for 1.5 Gbps
- [ ] Test with actual hardware for timing validation