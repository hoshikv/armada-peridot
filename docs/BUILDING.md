# Build notes

This repository preserves the source and assembly recipes behind a working local RAM build. It does not include enough binary inputs to generate a bootable image from a fresh clone alone. The original recipes retain the tested `/Volumes/DodgeGnomeBuild` layout and require a prepared Arch host initrd, Armada system root, board DT, exact generated kernel headers, firmware and custom UEFI.

## Tested versions

- Linux/Arch kernel: `7.3.0-1-aarch64-ARCH`, with exact matching generated headers.
- Official Armada userspace: `20261109.dfed5d6` (Plasma 6.8.2).
- Display: native KWin Wayland DRM/KMS, Mesa 26.2.6, Adreno 830 EGL.
- Fastfetch: official Linux aarch64 2.71.0 package.
- Native ARM Steam client: version `1788652215`, including its native Steam runtime.

The kernel source and generated headers must match the target kernel's ABI. Do not mix independently selected stock modules or use a Xiaomi 14 device tree on OnePlus 13. Houji was a source reference, not a drop-in board definition.

## Source and dependency chain

1. `experimental/armada-ram-v1/` records the official OCI userspace selection and original packaging. Its `manifest.json` pins component digests. The required Arch host initrd and initial board DT are local inputs.
2. `arch-gnome-touch-v1/` contains the S3910 userspace bridge, Linux multitouch/uinput integration and original session setup. The bridge requires the matching firmware lease prepared by custom UEFI, and the kernel's competing SPI controller disabled.
3. `arch-usb-control-v1/` adds the matching USB/clock/interconnect module loading and independent CDC recovery service.
4. `armada-native-v1/` adds Adreno/WCN7860 and native network startup. The module sources used for the successful build are preserved in `source/`; references and imported patch hashes remain in the corresponding metadata.
5. `armada-wayland-v1/` and `armada-hardware-v1/` add the panel/DSI fix, Wayland input classification, Bluetooth UART/power setup and display wake/buttons.
6. `armada-fastfetch-v1/` records fastfetch and 150% scaling.
7. `armada-steam-v1/` assembles the current compact desktop/native-client overlay. The filtered host initrd is regenerated automatically when absent. The exported extractor retains the native ARM runtime and applies the tested SONAME/affinity fixes; x86 game runtimes are excluded.
8. `armada-thermal-v1/build-fdt.py` adds the exact upstream SM8750 SCMI/CPUCP/SRAM and TSENS nodes, CPU performance domains and conservative cooling trips to the locally prepared hardware DT. `build-media.py` enables the thermal variant of the shared Steam image assembler.

Earlier recipe directories are dependencies and reference history, not a recommendation to use their unguarded images. Some upstream-fetch/UEFI preparation recipes also reference original workspace inputs outside this source snapshot; inspect their inputs before running them. The public boot helper requires an explicit device serial and allows a local image profile.

## Local inputs and paths

The assembly recipes expect, among other inputs:

- `/Volumes/DodgeGnomeBuild/armada-root`: extracted Armada userspace.
- `/Volumes/DodgeGnomeBuild/root`: prepared Arch host userspace.
- `/Volumes/DodgeGnomeBuild/steam-extra`: isolated native Steam files.
- `/Volumes/DodgeGnomeBuild/usb-kernel-headers`: exact generated Arch kernel headers.
- Matching built module directories, plus the prepared board DT and base `INITRD` under the original `experimental/` layout.
- Display/GPU, Wi-Fi and Bluetooth firmware acquired separately for your device. Local recipe paths under `diagnostics/` identify expected firmware inputs; raw diagnostics/calibration are intentionally not published.
- A compatible Project Boot UEFI with the RAM media, FDT, touch lease and USB recovery commands. See the related [ios-dodge source repository](https://github.com/faridbtw/ios-dodge); this snapshot does not independently build that complete UEFI bundle.

Host tools used include Homebrew Python, LLVM/LLD, GNU make and dtc, plus Apple clang and Android platform-tools. Kernel module build commands are recorded in `experimental/armada-native-v1/build-drivers.sh`. Kernel source slices retain their upstream includes and require the full matching kernel source/header environment; they are not standalone C libraries.

After recreating and reviewing the required local inputs, the final recipe is:

```sh
python3 experimental/armada-thermal-v1/build-fdt.py
python3 experimental/armada-thermal-v1/build-media.py
```

These generate a DTB, initrd overlay and FAT RAM media. The tested image is 2040 MiB, below the loader's 2047 MiB media limit. The builder checks FAT consistency. Rebuilt image hashes differ when packaging inputs or the embedded clock epoch change; update your ignored local boot profile with the actual output hashes.

## Cleanup and verification

`media/` staging, filtered initrd caches, downloaded archives and Python bytecode are disposable. Keep final working images, original roots, exact headers/modules, firmware, source trees and the modified extracted native client. The repository ignores generated images, binaries, system roots and raw diagnostics.

Run host policy tests with:

```sh
python3 experimental/armada-thermal-v1/test-thermal.py
```

The real-device thermal results are documented separately in [THERMAL.md](THERMAL.md) and `validation/thermal-build.json`. Host tests alone do not establish a working sensor/SCMI port on a different phone or firmware.
