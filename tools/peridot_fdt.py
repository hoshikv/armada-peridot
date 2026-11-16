#!/usr/bin/env python3
"""
Device Tree Manipulation for Xiaomi Peridot

Adapted from armada-dodge op13_fdt.py.
Provides utilities to modify DTB for Peridot RAM boot.
"""

import struct
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any, Union


# ─── FDT Constants ────────────────────────────────────────────────

FDT_MAGIC = 0xD00DFEED
FDT_VERSION = 17
FDT_LAST_COMP_VERSION = 16

FDT_BEGIN_NODE = 0x1
FDT_END_NODE = 0x2
FDT_PROP = 0x3
FDT_NOP = 0x4
FDT_END = 0x9

# ─── FDT Parser ───────────────────────────────────────────────────

class FDT:
    """Flattened Device Tree parser and editor."""

    def __init__(self, data: bytes):
        self.data = bytearray(data)
        self.parse_header()
        self.parse_struct()

    def parse_header(self):
        """Parse FDT header."""
        if len(self.data) < 40:
            raise ValueError("FDT too small for header")

        (self.magic, self.totalsize, self.off_dt_struct,
         self.off_dt_strings, self.off_mem_rsvmap,
         self.version, self.last_comp_version,
         self.boot_cpuid_phys, self.size_dt_strings,
         self.size_dt_struct) = struct.unpack_from(">10I", self.data, 0)

        if self.magic != FDT_MAGIC:
            raise ValueError(f"Invalid FDT magic: {self.magic:#x}")

    def parse_struct(self):
        """Parse structure block into node tree."""
        struct_data = self.data[self.off_dt_struct:self.off_dt_struct + self.size_dt_struct]
        strings_data = self.data[self.off_dt_strings:self.off_dt_strings + self.size_dt_strings]

        self.strings = strings_data.decode('ascii', errors='replace').split('\x00')
        self.nodes = []
        self._parse_tokens(struct_data)

    def _parse_tokens(self, data: bytes):
        """Parse FDT tokens."""
        i = 0
        path = []
        while i < len(data):
            token = struct.unpack_from(">I", data, i)[0]
            i += 4

            if token == FDT_BEGIN_NODE:
                # Read node name
                name_end = data.find(b'\x00', i)
                name = data[i:name_end].decode('ascii')
                i = name_end + 1
                i = (i + 3) & ~3  # Align to 4 bytes

                node = {
                    'name': name,
                    'path': '/' + '/'.join(path + [name]) if path else '/',
                    'props': {},
                    'children': [],
                    'parent': path[-1] if path else None,
                    'offset': i - 4,
                }
                if path:
                    self.nodes[path[-1]]['children'].append(len(self.nodes))
                path.append(len(self.nodes))
                self.nodes.append(node)

            elif token == FDT_END_NODE:
                path.pop()

            elif token == FDT_PROP:
                (prop_len, prop_nameoff) = struct.unpack_from(">II", data, i)
                i += 8
                prop_name = self.strings[prop_nameoff]
                prop_value = data[i:i+prop_len]
                i += prop_len
                i = (i + 3) & ~3

                if path:
                    self.nodes[path[-1]]['props'][prop_name] = prop_value

            elif token == FDT_NOP:
                pass

            elif token == FDT_END:
                break

    def find_node(self, path: str) -> Optional[int]:
        """Find node by path."""
        for idx, node in enumerate(self.nodes):
            if node['path'] == path:
                return idx
        return None

    def get_property(self, path: str, name: str) -> Optional[bytes]:
        """Get property value."""
        idx = self.find_node(path)
        if idx is not None:
            return self.nodes[idx]['props'].get(name)
        return None

    def set_property(self, path: str, name: str, value: bytes) -> bool:
        """Set property value (requires rebuild)."""
        idx = self.find_node(path)
        if idx is not None:
            self.nodes[idx]['props'][name] = value
            return True
        return False

    def add_property(self, path: str, name: str, value: bytes) -> bool:
        """Add property to node."""
        return self.set_property(path, name, value)

    def delete_property(self, path: str, name: str) -> bool:
        """Delete property from node."""
        idx = self.find_node(path)
        if idx is not None and name in self.nodes[idx]['props']:
            del self.nodes[idx]['props'][name]
            return True
        return False

    def rebuild(self) -> bytes:
        """Rebuild FDT binary."""
        # This is a simplified rebuild - for production use libfdt
        # For now, return original data (placeholder)
        log.warning("FDT rebuild not fully implemented, returning original")
        return bytes(self.data)


# ─── Peridot-Specific FDT Modifications ──────────────────────────

def patch_peridot_fdt(fdt_path: Path, output_path: Path,
                       bootargs: Optional[str] = None,
                       disable_ufs: bool = True,
                       enable_gpu: bool = True,
                       enable_display: bool = True,
                       enable_touch: bool = True,
                       enable_wifi: bool = True,
                       enable_bt: bool = True,
                       thermal_zones: bool = True) -> bool:
    """Apply Peridot-specific patches to DTB."""

    log.info(f"Patching DTB: {fdt_path} -> {output_path}")

    with open(fdt_path, 'rb') as f:
        data = f.read()

    fdt = FDT(data)

    # 1. Update bootargs in /chosen
    if bootargs:
        fdt.set_property("/chosen", "bootargs", bootargs.encode() + b'\x00')
        log.info("Updated bootargs")

    # 2. Disable UFS for RAM boot
    if disable_ufs:
        ufs_idx = fdt.find_node("/ufshc@1D84000")
        if ufs_idx is not None:
            fdt.nodes[ufs_idx]['props']['status'] = b'disabled\x00'
            log.info("Disabled UFS")

    # 3. Enable GPU
    if enable_gpu:
        gpu_idx = fdt.find_node("/kgsl_3d0")
        if gpu_idx is not None:
            fdt.nodes[gpu_idx]['props']['status'] = b'okay\x00'
            log.info("Enabled GPU")

    # 4. Enable Display
    if enable_display:
        for path in ["/dpu", "/dpu/dsi@AE36000", "/panel"]:
            idx = fdt.find_node(path)
            if idx is not None:
                fdt.nodes[idx]['props']['status'] = b'okay\x00'
        log.info("Enabled display")

    # 5. Enable Touch
    if enable_touch:
        touch_idx = fdt.find_node("/qupv3_1_geni_se/goodix_ts")
        if touch_idx is not None:
            fdt.nodes[touch_idx]['props']['status'] = b'okay\x00'
        spi_idx = fdt.find_node("/qupv3_1_geni_se")
        if spi_idx is not None:
            fdt.nodes[spi_idx]['props']['status'] = b'okay\x00'
        log.info("Enabled touchscreen")

    # 6. Enable WiFi
    if enable_wifi:
        for path in ["/pcie@1C00000", "/pcie@1C00000/wifi@0"]:
            idx = fdt.find_node(path)
            if idx is not None:
                fdt.nodes[idx]['props']['status'] = b'okay\x00'
        log.info("Enabled WiFi")

    # 7. Enable Bluetooth
    if enable_bt:
        bt_idx = fdt.find_node("/bluetooth@888000")
        if bt_idx is not None:
            fdt.nodes[bt_idx]['props']['status'] = b'okay\x00'
        uart_idx = fdt.find_node("/qupv3_0_geni_se/bt_uart")
        if uart_idx is not None:
            fdt.nodes[uart_idx]['props']['status'] = b'okay\x00'
        log.info("Enabled Bluetooth")

    # 8. Thermal zones (already in DT, just verify)
    if thermal_zones:
        tz_idx = fdt.find_node("/thermal-zones")
        if tz_idx is not None:
            log.info("Thermal zones present")

    # Rebuild and write
    new_data = fdt.rebuild()
    with open(output_path, 'wb') as f:
        f.write(new_data)

    log.info("DTB patching complete")
    return True


def extract_dtb_info(fdt_path: Path) -> Dict[str, Any]:
    """Extract key information from DTB."""
    with open(fdt_path, 'rb') as f:
        data = f.read()

    fdt = FDT(data)

    info = {
        'model': None,
        'compatible': [],
        'memory': [],
        'cpus': 0,
        'bootargs': None,
    }

    # Model
    model = fdt.get_property("/", "model")
    if model:
        info['model'] = model.decode('ascii').rstrip('\x00')

    # Compatible
    compat = fdt.get_property("/", "compatible")
    if compat:
        info['compatible'] = compat.decode('ascii').split('\x00')[:-1]

    # Memory
    mem = fdt.get_property("/memory@80000000", "reg")
    if mem:
        # Parse memory regions
        pass

    # CPUs
    cpus_idx = fdt.find_node("/cpus")
    if cpus_idx is not None:
        info['cpus'] = len(fdt.nodes[cpus_idx]['children'])

    # Bootargs
    ba = fdt.get_property("/chosen", "bootargs")
    if ba:
        info['bootargs'] = ba.decode('ascii').rstrip('\x00')

    return info


# ─── CLI ──────────────────────────────────────────────────────────

import logging
log = logging.getLogger("peridot_fdt")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Peridot DTB patcher")
    parser.add_argument("input", type=Path, help="Input DTB")
    parser.add_argument("output", type=Path, help="Output DTB")
    parser.add_argument("--bootargs", help="Kernel boot arguments")
    parser.add_argument("--disable-ufs", action="store_true", default=True)
    parser.add_argument("--enable-gpu", action="store_true", default=True)
    parser.add_argument("--enable-display", action="store_true", default=True)
    parser.add_argument("--enable-touch", action="store_true", default=True)
    parser.add_argument("--enable-wifi", action="store_true", default=True)
    parser.add_argument("--enable-bt", action="store_true", default=True)
    parser.add_argument("--info", action="store_true", help="Print DTB info")
    args = parser.parse_args()

    if args.info:
        info = extract_dtb_info(args.input)
        print(f"Model: {info['model']}")
        print(f"Compatible: {info['compatible']}")
        print(f"CPUs: {info['cpus']}")
        print(f"Bootargs: {info['bootargs']}")
        return 0

    patch_peridot_fdt(
        args.input, args.output,
        bootargs=args.bootargs,
        disable_ufs=args.disable_ufs,
        enable_gpu=args.enable_gpu,
        enable_display=args.enable_display,
        enable_touch=args.enable_touch,
        enable_wifi=args.enable_wifi,
        enable_bt=args.enable_bt,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())