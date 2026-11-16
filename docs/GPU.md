# GPU Support for Peridot (SM8635 / Adreno 735)

Adapted from armada-dodge GPU documentation for OnePlus 13 (SM8750 / Adreno 830).

## Hardware Specifications

| Property | Value |
|----------|-------|
| GPU | Adreno 735 |
| Chip ID | `0x43030B00` |
| GMU Version | `0x07020100` |
| Architecture | Gen 7 (A7xx family) |
| GMEM Size | 512 KB |
| Max Frequency | 800 MHz (capped to 222 MHz in practice) |
| SMMU | MMU-500 (v2) at `0x03DA0000` |

## Register Map (from xnu-kernel-peridot)

| Block | Base Address | Size | Description |
|-------|--------------|------|-------------|
| GPU CC | `0x03D90000` | `0xA000` | GPU Clock Controller |
| GMU | `0x03D68000` | `0x37000` | GPU Management Unit |
| GBIF | `0x03D0F000` | - | 3D Core Bus Interface |
| CX_MISC | `0x03D9E000` | `0x1000` | CX Misc Registers |
| RSCC | `0x03D50000` | `0x1000` | RPMh Sequencer Channel |
| SMMU | `0x03DA0000` | `0x40000` | GPU SMMU (MMU-500) |
| GCC (Global) | `0x00100000` | - | Global Clock Controller |

## Key GCC Clock Offsets

| Clock | Offset | Description |
|-------|--------|-------------|
| GCC_GPU_CFG_AHB | `0x71004` | GPU Config AHB |
| GCC_GPU_MEMNOC_GFX | `0x71010` | GPU MemNoc GFX |
| GCC_GPU_SNOC_DVM_GFX | `0x71018` | GPU SNoC DVM GFX |
| GCC_DDRSS_GPU_AXI | `0x7115C` | DDRSS GPU AXI |
| GCC_GPU_SMMU_CLK | `0x71160` | GPU SMMU Clock |

## Key GPUCC Register Offsets

| Register | Offset | Description |
|----------|--------|-------------|
| GPUCC_CX_GDSCR | `0x908C` | CX Power Domain Control |
| GPUCC_GX_GDSCR | `0x9034` | GX/3D Core Power Domain Control |
| GPUCC_CX_GMU_CBCR | `0x90E4` | GMU Clock Branch Control |
| GPUCC_AHB_CBCR | `0x90C8` | AHB Bus Clock Branch Control |

## Firmware Files

Required firmware files (from `/vendor/firmware_mnt/image` on device):

| File | Description |
|------|-------------|
| `a660_zap.mdt` | Zap shader binary (signed) |
| `a660_gmu.bin` | GMU firmware |
| `a660_sqe.fw` | SQE microcode |

These must be placed in `/lib/firmware/qcom/` or loaded via `request_firmware()`.

## Device Tree Integration

See `experimental/peridot-gpu-v1/sm8635-gpu.dtsi` for complete GPU DT.

Key nodes:
- `gpucc` - GPU clock controller
- `gpu_gdsc` - GPU power domains (CX, GX)
- `kgsl_3d0` - Main GPU device (GBIF + GMU + CX_MISC + RSCC)
- `gpu_smmu` - MMU-500 SMMU
- Reserved memory regions for GPU uncached/cached buffers

## Driver Patches

See `patches/armada/0049-drm-msm-add-adreno-735-peridot.patch` for kernel patches needed:

1. **adreno_gen7.c** - Add `a735_peridot_core` with correct chip ID, GMU version, frequencies
2. **a7xx_gmu.c** - Add `a735_peridot_gmu` with firmware names and HFI v3 features

## Kernel Config Options

```kconfig
CONFIG_DRM_MSM=y
CONFIG_DRM_MSM_ADRENO=y
CONFIG_DRM_MSM_ADRENO_A7XX=y
CONFIG_DRM_MSM_REGISTER_LOGGING=y
CONFIG_DEBUG_FS=y  # For GPU debugfs
```

## Userspace Requirements

### Mesa / Turnip (Vulkan)
- Mesa 24.0+ with Turnip driver
- `VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/turnic_icd.aarch64.json`

### OpenGL ES / EGL
- Mesa with `kgsl` platform support
- `EGL_PLATFORM_GBM_KHR` for Wayland

### Libdrm
- libdrm with `msm` driver
- `LIBDRM_MSM=1`

## Performance Notes

- **Frequency Cap**: In armada-dodge, GPU capped at 222 MHz for thermal stability
- **DCVS**: Dynamic Clock and Voltage Scaling enabled via GMU
- **Preemption**: Hardware preemption supported (CP_HWSCHED)
- **LLCC**: Last Level Cache Controller present
- **LM**: Local Memory (GMEM) 512 KB

## Thermal Integration

GPU thermal zone defined in `sm8635-thermal.dtsi`:
- Sensor: TSENS1 sensor 1 (and TSENS2)
- Trips: 70/80/85/90/95°C
- Cooling: Via GMU frequency scaling (separate from CPU SCMI)

## Debugging

### Check GPU Status
```bash
# Kernel log
dmesg | grep -i -e adreno -e gpu -e kgsl -e gmu

# Debugfs
ls /sys/kernel/debug/dri/0/
cat /sys/kernel/debug/dri/0/gpu_info
cat /sys/kernel/debug/dri/0/gmu_stats
```

### Frequency Control
```bash
# Current frequency
cat /sys/class/kgsl/kgsl-3d0/devfreq/cur_freq

# Available frequencies
cat /sys/class/kgsl/kgsl-3d0/devfreq/available_frequencies

# Set max frequency (for thermal cap)
echo 222000000 > /sys/class/kgsl/kgsl-3d0/devfreq/max_freq
```

### Firmware Loading
```bash
# Verify firmware files exist
ls -la /lib/firmware/qcom/a660_*

# Check firmware loading in dmesg
dmesg -T | grep -i firmware
```

## Known Issues / TODO

- [ ] Verify exact GPU CC register map for SM8635 (may differ from SM8750)
- [ ] Confirm GMU firmware version compatibility (0x07020100)
- [ ] Test DCVS stability at various frequencies
- [ ] Implement GPU cooling device driver for thermal framework
- [ ] Verify SMMU context bank allocation for GPU
- [ ] Test with actual Mesa/Turnip on Wayland
- [ ] Add GPU performance counters / profiling support