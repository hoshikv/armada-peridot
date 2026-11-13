#!/usr/bin/env python3
"""Boot the verified OnePlus 13 Armada image entirely in RAM."""
import argparse
from datetime import datetime, timezone
import fcntl
import glob
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / 'experimental/armada-thermal-v1/STATUS.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial', help='your OnePlus 13 adb/native-fastboot serial')
    parser.add_argument('--profile', type=Path, help='local STATUS profile with image paths and SHA256 values')
    parser.add_argument('--check', action='store_true', help='verify files only; no phone commands')
    parser.add_argument('--fastfetch', action='store_true', help='previous single-core fastfetch build without verified thermal controls')
    parser.add_argument('--hardware', action='store_true', help='boot previous verified Bluetooth/button build at 125 percent without fastfetch')
    parser.add_argument('--wayland', action='store_true', help='alias for --hardware: newer verified Wayland fallback')
    parser.add_argument('--x11', action='store_true', help='boot the preserved verified X11 desktop')
    parser.add_argument('--fallback', action='store_true', help='boot the older verified software-rendered recovery build')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if sum([args.x11,args.fallback,args.wayland,args.hardware,args.fastfetch]) > 1:
        parser.error('Choose at most one fallback option')
    selected_state = ROOT / 'experimental/armada-native-v1/STATUS.json' if args.x11 or args.fallback else (ROOT / 'experimental/armada-hardware-v1/STATUS.json' if args.wayland or args.hardware else (ROOT / 'experimental/armada-fastfetch-v1/STATUS.json' if args.fastfetch else STATE))
    if args.profile:selected_state=args.profile.resolve()
    status = json.loads(selected_state.read_text())
    if not args.check and not args.serial:parser.error('--serial is required for phone operations')
    if args.serial:status['serial']=args.serial
    if not status['runtime_verified'] or status['phone_storage_writes']:
        raise SystemExit('Expected a verified RAM-only build in STATUS.json')
    if args.fallback:
        status['media'] = status['fallback_media']
        status['media_sha256'] = status['fallback_media_sha256']
    files = {}
    for name in ['media', 'uefi']:
        path = (ROOT / status[name]).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise SystemExit(f'Missing verified {name}: {path}')
        with path.open('rb') as source:
            digest = hashlib.file_digest(source, 'sha256').hexdigest()
        if digest != status[name + '_sha256']:
            raise SystemExit(f'{name} checksum differs from the verified build; stop and inspect STATUS.json')
        files[name] = path
    print('Verified Armada RAM image and Project Boot UEFI checksums.', flush=True)
    if args.check:
        print('No phone commands were sent.')
        return

    # This lock prevents two invocations of this helper from sharing USB.
    with (ROOT / 'experimental/armada-native-v1/.boot-usb.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('Another Armada boot helper is already using USB')
        output = args.output or ROOT / 'diagnostics' / ('armada-boot-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S'))
        output = output.resolve()
        output.mkdir(parents=True, exist_ok=False)
        client = ROOT / 'experimental/armada-thermal-v1/control-phone.py'
        ports = glob.glob('/dev/cu.usbmodemOP13RAMCONTROL*')
        if ports:
            if len(ports) != 1:
                raise SystemExit('Expected exactly one OnePlus RAM USB recovery connection')
            print('Restarting the current RAM session into Android.', flush=True)
            subprocess.run([sys.executable, str(client), 'reboot', '--output', str(output / 'reboot-ack.txt')], check=True, timeout=50)
        print('Connect the matched phone in Android or native fastboot. Upload may take several minutes.', flush=True)
        subprocess.run([sys.executable, str(ROOT / 'tools/boot-op13-multiboot.py'),
                        '--serial', status['serial'], '--image', str(files['uefi']),
                        '--media', str(files['media']), '--output', str(output / 'stage')],
                       check=True, timeout=600)
        receipts = []
        for operation in [['oem', 'linux-fdt-use'], ['oem', 'linux-touch-arm'], ['oem', 'log'],
                          ['get_staged', str(output / 'touch-prelaunch-loader.log')], ['oem', 'boot-linux']]:
            command = ['fastboot', '-s', 'xnuloader', *operation]
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
            receipts.append({'args': command, 'exit': result.returncode, 'output': result.stdout + result.stderr})
            (output / 'launch-receipts.json').write_text(json.dumps(receipts, indent=2) + '\n')
            result.check_returncode()
        print('Armada launched in RAM. Waiting for Linux USB recovery.', flush=True)
        deadline = time.monotonic() + 100
        while time.monotonic() < deadline:
            if glob.glob('/dev/cu.usbmodemOP13RAMCONTROL*'):
                result = subprocess.run([sys.executable, str(client), 'status', '--output', str(output / 'linux-status.json')], timeout=25)
                if result.returncode == 0:
                    if status.get('clock_sync_supported'):
                        subprocess.run([sys.executable, str(client), 'clocksync', '--output', str(output / 'clock-sync.json')],check=True,timeout=30)
                    if status.get('thermal_runtime_verified'):
                        previous=None
                        for _ in range(65):
                            r=subprocess.run([sys.executable,str(client),'thermalstatus','--output',str(output/'thermal-state.json')],timeout=25)
                            if r.returncode==0:
                                state=json.loads((output/'thermal-state.json').read_text())['state']
                                if state.get('phase')=='ready' and state.get('online')=='0-7' and previous is not None and state['monotonic']>previous:break
                                previous=state.get('monotonic')
                            time.sleep(1)
                        else:raise SystemExit('Thermal controls did not become ready; inspect boot logs')
                        print('Temperature sensors, eight CPUs and thermal limits are ready.')
                    print(f'Armada USB recovery is reachable. Boot logs: {output}')
                    return
            time.sleep(1)
        raise SystemExit(f'Linux launch was accepted but USB did not return. Check the phone screen. Logs: {output}')


if __name__ == '__main__':
    main()
