#!/usr/bin/env bash
# Run after applying patches.json's patches to the official Linux 7.3 source.
# Builds modules only, with the exact installed Arch kernel's generated headers.
set -euo pipefail
here=$(cd -- "$(dirname -- "$0")" && pwd)
headers=/Volumes/DodgeGnomeBuild/usb-kernel-headers/usr/lib/modules/7.3.0-1-aarch64-ARCH/build
source_root=/Volumes/DodgeGnomeBuild/usb-linux-source/linux-7.3
project=$(cd -- "$here/../.." && pwd)
for pair in "ath12k:drivers/net/wireless/ath/ath12k" "msm:drivers/gpu/drm/msm" "providers:/Volumes/DodgeGnomeBuild/native-modules"; do
 name=${pair%%:*};module=${pair#*:}
 [[ "$module" == /* ]] || module="$source_root/$module"
 /opt/homebrew/bin/gmake -C "$headers" M="$module" ARCH=arm64 \
  LLVM=/opt/homebrew/opt/llvm/bin/ LD=/opt/homebrew/bin/ld.lld \
  CROSS_COMPILE=aarch64-linux-gnu- HOSTCC=/usr/bin/clang \
  "HOSTCFLAGS=-O2 -I$project/experimental/arch-usb-control-v1/host-include -I$headers/scripts/include" \
  'KCFLAGS=-Wno-error=unknown-warning-option -Wno-error=unused-command-line-argument' \
  PYTHON3=/opt/homebrew/bin/python3 -j6 modules >"$here/build-$name.log" 2>&1
done
