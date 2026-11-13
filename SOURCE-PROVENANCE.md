# Sources and credits

This repository records a source snapshot of the OnePlus 13 RAM bring-up verified on 13 November 2026. The original prepared workspace and generated artifacts remain local. Upstream copyright notices and SPDX identifiers are retained in the imported code.

| Source | Pinned reference / use |
| --- | --- |
| [Armada](https://github.com/armada-os/armada) | Userspace `20261109.dfed5d6`; OCI manifest SHA256 `0f0c990818303ae621c7bcbd10979409aa1143a12e2457f3c0c0452652d35d73`; source reference checkout `b031deef99a095104ef234c5a0705850152dffe1` |
| [armada-houji](https://github.com/yoni13/armada-houji) | `3311a74651c16be81ac5cc5de32382fa140cce61`; SM8750/Adreno/WCN7860 reference, not a board DT replacement |
| [linux-omarchy-mobile](https://github.com/mrlund/linux-omarchy-mobile) | `6cc4b65df980355e00417df3d4b7b8109e7d0d21`; Dodge panel, Bluetooth and MDSS wake references |
| [omarchy-mobile](https://github.com/derekross/omarchy-mobile) | Dodge notes/reference audit; userspace reference `12258d9168241568416390a5b1d755b7018d475b` |
| [Linux](https://www.kernel.org/) | Exact Linux 7.3 source; archive SHA256 `87363c24f10e06321eb362765521094e94471f6bff8bce2d6b3e40f39f004953` |
| Arch Linux ARM kernel | `linux-aarch64-7.3-1-aarch64.pkg.tar.xz`; SHA256 `8f3d279f54239bcb7c11add4cd413df9761b3e36556602f2292290fca66f9906`; exact generated headers required |
| [fastfetch](https://github.com/fastfetch-cli/fastfetch) | Official Linux aarch64 2.71.0 archive SHA256 `458248f2b3abab9c5e0a5b9df12cdcd1a966b355ddd5f3244a5eb47d17d33412`; binaries not included |
| Steam component in official Armada OCI image | Native ARM client version `1788652215`; layer SHA256 `28580b759fac925cdfae560cf9f4109ad64cc07a3433e41368bf30bf1aaf1115`, size 1,783,648,541 bytes; client/runtime binaries not included |

`source/linux/drivers/gpu/drm/msm` preserves the source slice used for the tested wake-capable DRM/MSM module, including the Adreno 830 and DSC command-format adaptations. `source/linux/drivers/net/wireless/ath/ath12k` preserves the tested WCN7860 source slice. `source/linux/drivers/bluetooth` contains the pinned Dodge QCA sources. Display/clock/power-provider source slices are in `source/modules`. These depend on the full matching Linux source/generated-header environment.

`patches/armada` retains attributed Armada kernel patches. The MDSS wake reference is in `patches/dodge`; the DSC RGB888 command-format patch is also preserved in `experimental/armada-wayland-v1`. The thermal DTSI uses upstream SM8750 nodes and Armada's CPU cooling maps. Conservative trip selection and RAM guard integration are local port changes.

The S3910 userspace bridge retains its BSD-2-Clause SPDX headers. Linux-derived code retains its individual SPDX declarations (including GPL and BSD variants). Applicable upstream license texts are collected under `licenses/linux`. This document does not relicense upstream files or assign one blanket license to this mixed-source snapshot.

There are no firmware binaries, device calibration, serial-numbered phone captures, account credentials, complete system images or Apple SDK/system files in this export. `SOURCE-MANIFEST.json` inventories the published source files; `validation/thermal-build.json` contains curated verification facts rather than raw logs.
