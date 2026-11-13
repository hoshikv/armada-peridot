#!/usr/bin/env python3
"""Isolated Project Boot v25 UI plus validated Linux RAM-drive boot support."""
from pathlib import Path
import shutil,json,hashlib
p=Path(__file__).resolve().parent;root=p.parents[1];src=root/'experimental/wifi/darwin-handoff-v25/loader-src';old=root/'experimental/arch-gnome-touch-v1/loader-src';out=p/'project-boot/loader-src'
if out.exists():raise SystemExit('Source already prepared; inspect existing changes')
shutil.copytree(src,out)
for name in ['efi.h','op13_multiboot.h','op13_multiboot.inc']:shutil.copyfile(old/name,out/name)
f=out/'loader.c';s=f.read_text()
def replace(a,b):
 global s
 assert s.count(a)==1,(a,s.count(a));s=s.replace(a,b)
replace('#define PAYLOAD_MAX_SIZE    0x04000000ULL','#define PAYLOAD_MAX_SIZE    0x80000000ULL')
replace('''efi_status payload_status = BS->allocate_pages(AllocateAddress, EfiLoaderData,
        PAYLOAD_MAX_SIZE >> 12, &payload_address);
    if (EFI_ERROR(payload_status)) {
        payload_address = 0xFFFFFFFFULL;
        payload_status = BS->allocate_pages(AllocateMaxAddress, EfiLoaderData,
            PAYLOAD_MAX_SIZE >> 12, &payload_address);
    }''','''efi_status payload_status = BS->allocate_pages(AllocateAnyPages, EfiLoaderData,
        PAYLOAD_MAX_SIZE >> 12, &payload_address);''')
replace('#include "op13_boot_menu.inc"','#include "op13_multiboot.inc"\n#include "op13_boot_menu.inc"')
replace('    screen_quiet = busy;','    if (mb_command(cmd)) return;\n    screen_quiet = busy;')
replace('uint64_t total = parse_number(cmd + 9, 16), got = 0;','uint64_t total = parse_number(cmd + 9, 16), got = 0;\n            if (mb_registered) { fb_reply("FAIL", "unmount-media before replacing mounted RAM drive"); return; }\n            mb_staged_size=0;')
replace('if(to_wmi)op13_wifi_wmi_mailbox_size=(unsigned)total;','if(!to_wmi&&!to_ramdisk)mb_staged_size=total;\n                if(to_wmi)op13_wifi_wmi_mailbox_size=(unsigned)total;')
replace('"0x03f00000"','"0x7ff00000"')
# The Linux variant must never enter the iOS payload prepare/run path.
replace('if (mb_command(cmd)) return;','if (str_eq(cmd,"oem menu-prepare")) { fb_reply("FAIL","Linux launches from the Mac; no iOS payload loaded"); return; }\n    if (mb_command(cmd)) return;')
f.write_text(s)
f=out/'op13_multiboot.inc';s=f.read_text().replace('static int mb_command(const char *cmd)\n{','static int mb_command(const char *cmd)\n{\n    if (str_eq(cmd,"getvar:boot-target")) { fb_reply("OKAY","linux-windows-arm64"); return 1; }\n    if (starts_with(cmd,"oem menu-") && !str_eq(cmd,"oem menu-prepare")) return 0;');f.write_text(s)
# Keep the current layout, native font, turtle, safe Logs controls and Android card.
# Boot is automatic from the host; the inactive first card states this explicitly.
f=out/'op13_menu_ui.h'
if not f.exists():f=next(x for x in out.glob('op13_menu*') if 'Boot iOS' in x.read_text())
s=f.read_text().replace('Boot iOS','Boot Armada').replace('Waiting for iOS files','Launch from your Mac').replace('Preparing iOS in RAM...','Preparing Armada in RAM...').replace('iOS ready in RAM','Armada ready in RAM').replace('Connect to your Mac to prepare iOS','Connect to your Mac to prepare Armada');f.write_text(s)
receipt={'base':'experimental/wifi/darwin-handoff-v25','base_image_sha256':hashlib.sha256((src.parent/'dodge-ios-uefi.img').read_bytes()).hexdigest(),'ui':'Project Boot themed menu and scrolling Logs panel; host-driven Linux launch','phone_tested':False,'storage_writes':False}
(p/'project-boot/PROVENANCE.json').write_text(json.dumps(receipt,indent=2))
print('Prepared isolated Project Boot Linux source:',out)
