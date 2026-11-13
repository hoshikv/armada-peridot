#!/usr/bin/env python3
"""RAM-boot the separate ARM64 EFI manager and optionally launch supplied FAT media."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial', required=True)
    parser.add_argument('--image', type=Path, default=ROOT / 'experimental/multiboot/linux-windows-v1/dodge-uefi.img')
    parser.add_argument('--media', type=Path)
    parser.add_argument('--os', choices=['linux', 'windows'])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--wait-seconds', type=int, default=180)
    args = parser.parse_args()
    if args.os and not args.media:
        parser.error('--os requires explicitly supplied --media; test media is not an operating system')
    image = args.image.resolve()
    receipt = json.loads(image.with_suffix('.json').read_text())
    assert hashlib.sha256(image.read_bytes()).hexdigest() == receipt['image_sha256']
    if args.media:
        args.media = args.media.resolve()
        size = args.media.stat().st_size
        with args.media.open('rb') as file:
            sector = file.read(512)
        if not 2048 <= size <= 0x7ff00000 or size % 512 or sector[510:512] != b'\x55\xaa':
            parser.error('Media must be a raw FAT drive, at most 2047 MiB; use make-op13-efi-media.py')
        if sector[11:13] != b'\0\x02' or b'FAT' not in sector[54:90]:
            parser.error('Use a FAT volume image, not an ISO or partitioned disk image')
    output = args.output or ROOT / 'diagnostics' / ('multiboot-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S'))
    output.mkdir(parents=True, exist_ok=False)
    events = []

    def command(argv, timeout=10, check=True):
        began = time.monotonic()
        try:
            p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            events.append({'args': argv, 'timeout': timeout})
            (output / 'receipts.json').write_text(json.dumps(events, indent=2) + '\n')
            raise
        events.append({'args': argv, 'exit': p.returncode, 'seconds': time.monotonic() - began,
                       'output': p.stdout + p.stderr})
        (output / 'receipts.json').write_text(json.dumps(events, indent=2) + '\n')
        if check:
            p.check_returncode()
        return p

    def fb(argv, serial='xnuloader', timeout=10, check=True):
        # Fixed RAM operations only. No flash, erase, boot-variable or partition writes.
        return command(['fastboot', '-s', serial, *argv], timeout, check)

    devices = command(['fastboot', 'devices']).stdout
    already_manager = False
    if 'xnuloader' in devices:
        target = fb(['getvar', 'boot-target'], timeout=5)
        already_manager = 'linux-windows-arm64' in target.stdout + target.stderr
        if not already_manager:
            status = fb(['getvar', 'result'], timeout=5)
            if 'result: idle' not in status.stdout + status.stderr:
                raise SystemExit('The existing loader is busy; restart the phone into Android')
            fb(['reboot'])
    if not already_manager:
        print('Waiting for the matched phone in Android or its bootloader', flush=True)
        deadline = time.monotonic() + args.wait_seconds
        while time.monotonic() < deadline:
            state = command(['adb', '-s', args.serial, 'get-state'], check=False)
            if state.returncode == 0 and state.stdout.strip() == 'device':
                board = command(['adb', '-s', args.serial, 'shell', 'getprop ro.board.platform']).stdout.strip()
                assert board == 'sun', 'Unexpected Android platform'
                ready = command(['adb', '-s', args.serial, 'shell', 'getprop sys.boot_completed']).stdout.strip()
                if ready != '1':
                    time.sleep(1)
                    continue
                command(['adb', '-s', args.serial, 'reboot', 'bootloader'])
            listed = command(['fastboot', 'devices']).stdout
            if args.serial in listed:
                product = fb(['getvar', 'product'], args.serial, 3)
                assert 'sun' in product.stdout + product.stderr, 'Unexpected fastboot platform'
                break
            time.sleep(1)
        else:
            raise SystemExit('Phone unavailable; restart into Android. No image booted.')
        fb(['boot', str(image)], args.serial, 30)
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            listed = command(['fastboot', 'devices']).stdout
            if 'xnuloader' in listed:
                break
            time.sleep(.5)
        else:
            raise SystemExit('Image sent; RAM loader USB not confirmed')
    target = fb(['getvar', 'boot-target'], timeout=5)
    assert 'linux-windows-arm64' in target.stdout + target.stderr, 'Not the multiboot build'
    if args.media:
        fb(['oem', 'unmount-media'], timeout=20)
        print('Uploading supplied FAT boot media into RAM', flush=True)
        fb(['stage', str(args.media)], timeout=180)
        fb(['oem', 'mount-media'], timeout=30)
    fb(['oem', 'multiboot-info'])
    if args.os:
        fb(['oem', 'boot-' + args.os], timeout=30)
        print('EFI launch requested for ' + args.os + '; operating-system boot success is not confirmed.', flush=True)
    else:
        fb(['oem', 'log'])
        fb(['get_staged', str(output / 'loader.log')], timeout=30)
        print('Separate Linux/Windows ARM64 EFI manager ready.', flush=True)
    (output / 'RESULT.json').write_text(json.dumps({
        'manager_ready': True, 'requested_os': args.os, 'os_boot_confirmed': False,
        'media_supplied': bool(args.media), 'phone_partition_writes': False,
    }, indent=2) + '\n')


if __name__ == '__main__':
    main()
