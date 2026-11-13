#!/usr/bin/env python3
"""Create a raw FAT32 RAM boot drive from a directory (no mounts or phone access)."""
import argparse
import math
from pathlib import Path
import struct


def build(source, output, mib):
    if not 64 <= mib <= 2047:
        raise ValueError('Use 64..2047 MiB for the multiboot staging buffer')
    sector, reserved, copies = 512, 32, 2
    total, spc = mib * 2048, (1 if mib < 256 else 8)
    fat_sectors = 1
    while True:
        clusters = (total - reserved - copies * fat_sectors) // spc
        needed = math.ceil((clusters + 2) * 4 / sector)
        if needed <= fat_sectors:
            break
        fat_sectors = needed
    if clusters < 65525:
        raise ValueError('Volume is too small for FAT32')
    cluster_bytes = spc * sector
    fat = bytearray(fat_sectors * sector)
    struct.pack_into('<II', fat, 0, 0x0ffffff8, 0xffffffff)
    next_cluster = 2
    nodes = []

    def allocate(count):
        nonlocal next_cluster
        if next_cluster + count > clusters + 2:
            raise ValueError('Media is full; increase --size-mib')
        chain = list(range(next_cluster, next_cluster + count))
        next_cluster += count
        for i, c in enumerate(chain):
            struct.pack_into('<I', fat, c * 4, chain[i+1] if i+1 < len(chain) else 0x0fffffff)
        return chain

    def tree(path, parent=None):
        node = {'path': path, 'parent': parent, 'directory': path.is_dir(), 'children': []}
        nodes.append(node)
        if node['directory']:
            names = set()
            for child in sorted(path.iterdir(), key=lambda p: p.name.casefold()):
                if child.is_symlink():
                    raise ValueError('Symlinks are not supported: ' + str(child))
                if not child.is_file() and not child.is_dir():
                    raise ValueError('Unsupported file type: ' + str(child))
                if child.name.casefold() in names:
                    raise ValueError('Case-insensitive duplicate name: ' + child.name)
                names.add(child.name.casefold())
                node['children'].append(tree(child, node))
        else:
            node['size'] = path.stat().st_size
            if node['size'] > 0xffffffff:
                raise ValueError('FAT files must be smaller than 4 GiB')
        return node

    root = tree(source)
    # Assign directory/file chains together, starting with the root at cluster2.

    def aliases(directory):
        used = set()
        for child in directory['children']:
            name = child['path'].name
            if any(c in name for c in '\\/:*?"<>|'):
                raise ValueError('Invalid FAT filename: ' + name)
            units = name.encode('utf-16-le')
            if len(units) > 510:
                raise ValueError('Filename exceeds 255 UTF16 units')
            base, dot, ext = name.rpartition('.')
            if not dot or not base:
                base, ext = name, ''
            base, ext = base.upper(), ext.upper()
            clean = lambda v: ''.join(c for c in v if c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_$~!#%&-{}()@'`")
            simple = (base == clean(base) and ext == clean(ext) and 1 <= len(base) <= 8 and len(ext) <= 3)
            short = base.ljust(8) + ext.ljust(3) if simple else ''
            number = 1
            while not short or short in used:
                suffix = '~' + str(number)
                short = (clean(base) or 'FILE')[:8-len(suffix)].ljust(8-len(suffix), '_') + suffix + clean(ext)[:3].ljust(3)
                number += 1
            used.add(short)
            child['short'] = short.encode('ascii')
            child['lfn'] = units
        entries = 0 if directory['parent'] is None else 2
        entries += sum(math.ceil((len(c['lfn']) // 2 + 1) / 13) + 1 for c in directory['children'])
        directory['chain'] = allocate(max(1, math.ceil((entries + 1) * 32 / cluster_bytes)))
        for child in directory['children']:
            if child['directory']:
                aliases(child)
            else:
                child['chain'] = allocate(math.ceil(child['size'] / cluster_bytes))

    aliases(root)
    assert root['chain'][0] == 2
    data_sector = reserved + copies * fat_sectors
    boot = bytearray(512)
    boot[:11] = b'\xeb\x58\x90DODGEMB '
    struct.pack_into('<HBHBHHBHHHII', boot, 11, 512, spc, reserved, copies, 0, 0, 0xf8, 0, 63, 255, 0, total)
    struct.pack_into('<IHHIHH', boot, 36, fat_sectors, 0, 0, 2, 1, 6)
    boot[64:67] = b'\x80\0\x29'
    struct.pack_into('<I', boot, 67, 0x13000001)
    boot[71:82] = b'DODGE RAM  '
    boot[82:90] = b'FAT32   '
    boot[510:512] = b'\x55\xaa'
    info = bytearray(512)
    struct.pack_into('<I', info, 0, 0x41615252)
    struct.pack_into('<IIII', info, 484, 0x61417272, clusters - (next_cluster - 2), next_cluster, 0)
    struct.pack_into('<I', info, 508, 0xaa550000)

    def entry(name, attributes, cluster, size=0):
        e = bytearray(32); e[:11] = name
        e[11] = attributes
        struct.pack_into('<H', e, 20, cluster >> 16)
        struct.pack_into('<H', e, 26, cluster & 0xffff)
        struct.pack_into('<I', e, 28, size)
        # Fixed valid FAT date, independent of local private file timestamps.
        struct.pack_into('<H', e, 24, ((2026 - 1980) << 9) | 1 << 5 | 1)
        return e

    def directory_bytes(node):
        out = bytearray()
        if node['parent'] is not None:
            out += entry(b'.          ', 16, node['chain'][0])
            parent = node['parent']
            out += entry(b'..         ', 16, 0 if parent is root else parent['chain'][0])
        for child in node['children']:
            checksum = 0
            for c in child['short']:
                checksum = (((checksum & 1) << 7) + (checksum >> 1) + c) & 255
            name = child['lfn'] + b'\0\0'
            count = math.ceil(len(name) / 26)
            name += b'\xff\xff' * ((count * 26 - len(name)) // 2)
            for part in range(count, 0, -1):
                e = bytearray(32); e[0] = part | (0x40 if part == count else 0)
                e[11] = 15; e[13] = checksum
                chunk = name[(part-1)*26:part*26]
                e[1:11] = chunk[:10]; e[14:26] = chunk[10:22]; e[28:32] = chunk[22:26]
                out += e
            out += entry(child['short'], 16 if child['directory'] else 32,
                         child['chain'][0] if child['chain'] else 0, 0 if child['directory'] else child['size'])
        return out

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('wb') as image:
        image.truncate(total * sector)
        for block, content in [(0, boot), (1, info), (6, boot), (7, info)]:
            image.seek(block * sector); image.write(content)
        for i in range(copies):
            image.seek((reserved + i * fat_sectors) * sector); image.write(fat)
        for node in nodes:
            if node['directory']:
                content = directory_bytes(node)
                for i, cluster in enumerate(node['chain']):
                    image.seek((data_sector + (cluster - 2) * spc) * sector)
                    image.write(content[i*cluster_bytes:(i+1)*cluster_bytes])
            else:
                with node['path'].open('rb') as file:
                    for cluster in node['chain']:
                        image.seek((data_sector + (cluster - 2) * spc) * sector)
                        image.write(file.read(cluster_bytes))
    return {'bytes': total * sector, 'files': sum(not n['directory'] for n in nodes), 'fat': 32}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--size-mib', type=int, default=64)
    args = parser.parse_args()
    source, output = args.directory.resolve(), args.output.resolve()
    if not source.is_dir() or output.is_relative_to(source):
        parser.error('Use a source directory and an output image outside that directory')
    print(build(source, output, args.size_mib))


if __name__ == '__main__':
    main()
