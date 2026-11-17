# LinuxLoader for Peridot UEFI

This directory contains the Mu-Silicium UEFI side used to bring up Linux on
Xiaomi Peridot (SM8635) without flashing.

## Verified working reference

The last known-good UEFI console boot is preserved as:

| Item | Value |
| --- | --- |
| Boot image | `Mu-peridot-linux-console.img` |
| SHA-256 | `91abe3430d143cd098ef2d9304d75127c470d44c7636067dc0b460b63cbc5a82` |
| Size | 17,592,320 bytes |
| UEFI FD | `SILICIUM_UEFI.fd` in this directory |
| FD SHA-256 | `28c428e8fb54c28066b0c0e30be5517041b5d2e915e6a381e582a37a02aa59ec` |
| Initrd | `initrd-console60.img` (diagnostic, auto poweroff after about 60 s) |
| Initrd SHA-256 | `8d58d219bc515317ef92804ab983cdfba0ad9d23fe38f160bca7c683ac754552` |
| Kernel cmdline | `console=tty0 loglevel=7 ignore_loglevel` |

Boot command:

```sh
fastboot boot Mu-peridot-linux-console.img
```

Verified result: the kernel reaches the Linux console. The framebuffer is
efifb (`/proc/fb` reports `0 EFI VGA`, 1220x2712x32, stride 4880, fbcon
152x169). The test initrd powers the device off after about 60 seconds.

This exact boot image is the working reference. Later no-poweroff, efifb-only,
and earlycon variants did not reach the console, so do not treat them as
equivalent.

## Contents

- `LinuxLauncher.c` / `LinuxLauncher.inf`: UEFI DXE driver that parses the XNUP
  payload, installs the DTB as the EFI FDT configuration table, publishes the
  initrd through `EFI_LOAD_FILE2_PROTOCOL` using
  `LINUX_EFI_INITRD_MEDIA_GUID`, and starts the Linux EFI stub at
  `ReadyToBoot`.
- `SILICIUM_UEFI.fd`: the 3 MiB FD from the verified build above.
- `patches/0001-peridot-add-linuxlauncher.patch`: the Mu-Silicium DSC/FDF
  integration changes for this driver.

The boot image itself is not committed because this repository ignores `*.img`
and because it contains the test initrd; its SHA-256 is recorded above.

## Payload layout

`LinuxLauncher` expects the load address `0xF0000000` to contain an XNUP
payload. The payload is built by
`xnu-kernel-peridot/xnuloader/mkpayload.py` with these entries:

| Name | Contents |
| --- | --- |
| `Image` | Linux arm64 `Image` |
| `dtb` | Peridot DTB, including `/chosen/bootargs` |
| `ramdisk` | initramfs |
| `cmdline` | Linux command line |

The payload is limited to 64 MiB by `PAYLOAD_MAX_SIZE` in `LinuxLauncher.c`.
The driver reserves the payload as `EfiRuntimeServicesData` at its load address,
and falls back to an `EfiLoaderData` copy if that reservation fails. Keep that
behavior: the payload at `0xF0000000` is not guaranteed to be untouched by
UEFI otherwise.

The full boot image is assembled as:

```text
gzip(BootShim.bin + SILICIUM_UEFI.fd + XNUP payload) + original peridot.dtb
```

and wrapped with an Android/Qualcomm boot image. The previous verified image
used `mkbootimg.py --header_version 4 --pagesize 4096`.

## Build integration

Apply the included patch from the Mu-Silicium root, or add the driver manually:

- Copy `LinuxLauncher/` to
  `Silicon/Silicium/SiliciumPkg/Applications/LinuxLauncher/`.
- Add `SiliciumPkg/Applications/LinuxLauncher/LinuxLauncher.inf` to
  `Platforms/Xiaomi/peridotPkg/peridot.dsc`.
- Add `INF SiliciumPkg/Applications/LinuxLauncher/LinuxLauncher.inf` to the DXE
  section of `Platforms/Xiaomi/peridotPkg/peridot.fdf`.

The verified FD was built with the CLANGPDB debug configuration and the
peridot FD base/size used by the existing Mu-Silicium build. The FD is nearly
full, so keep an eye on FV space when adding more DXE drivers.

## Armada RAM media status

The Armada builder artifact contains `peridot-media.img` (2 GiB FAT32, label
`PERIDOT`) with:

- `boot/Image`, `boot/initrd.img`, `boot/peridot.dtb`, `boot/boot.conf`
- `modules/`, `firmware/`, `thermal/`
- optional `arch/`, `armada/`, and `steam/` userspace trees

The `boot/initrd.img` currently in that media is the same diagnostic busybox
initramfs used by the flashless `peridot-boot.img`; it prints the kernel/module
status and then drops to a rescue shell. It does not mount the FAT media or
switch to a desktop rootfs.

The current UEFI `LinuxLauncher` only hands the kernel `Image`, DTB, and
`ramdisk`. Loading the 2 GiB FAT media through UEFI and handing it to that
initramfs is not implemented here yet. The direct
`fastboot boot peridot-boot.img` path from the builder is a bring-up artifact,
not the UEFI path.

## UEFI notes

- The `ReadyToBoot` notification must use a TPL above `TPL_APPLICATION`.
  `TPL_CALLBACK` is the verified setting; `TPL_APPLICATION` is rejected by
  EDK2's `CreateEventEx` and results in the UEFI firmware finding no OS.
- Keep `InstallConfigurationTable(gFdtTableGuid)` before `LoadImage`; the EFI
  stub consumes the DTB from the configuration table.
- The initrd `LoadFile2` implementation must return `EFI_BUFFER_TOO_SMALL` with
  the required size when the caller's buffer is too small, then copy on the
  retry.
- Warm reboots can leave the Goodix touch controller unavailable until a full
  power cycle; that is unrelated to the loader.
