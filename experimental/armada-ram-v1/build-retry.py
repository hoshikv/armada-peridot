#!/usr/bin/env python3
"""Append a small corrected session overlay; retain the original test media."""
from pathlib import Path
import gzip,hashlib,json,stat,subprocess,sys
p=Path(__file__).resolve().parent;media=p/'media';marker=p/'retry-overlay.json'
size=json.loads(marker.read_text())['base_initrd_bytes'] if marker.exists() else (media/'INITRD').stat().st_size
entries={}
for f in p.glob('armada-*.sh'):
 subprocess.run(['/bin/bash','-n',str(f)],check=True);entries['armada/'+f.name]=f.read_bytes()
subprocess.run(['/bin/bash','-n',str(p/'host-session.sh')],check=True)
entries['host-session.sh']=(p/'host-session.sh').read_bytes()
archive=bytearray();ino=1
def add(name,mode,data=b''):
 global ino
 n=name.encode()+b'\0';v=[ino,mode,0,0,1,0,len(data),0,0,0,0,len(n),0]
 archive.extend(b'070701'+b''.join(f'{x:08x}'.encode() for x in v)+n);archive.extend(b'\0'*(-len(archive)%4));archive.extend(data);archive.extend(b'\0'*(-len(archive)%4));ino+=1
add('armada',stat.S_IFDIR|0o755)
for name,data in entries.items():add(name,stat.S_IFREG|0o755,data)
add('TRAILER!!!',0)
overlay=gzip.compress(archive,mtime=0)
with (media/'INITRD').open('r+b') as f:f.truncate(size);f.seek(size);f.write(overlay)
marker.write_text(json.dumps({'base_initrd_bytes':size,'overlay_sha256':hashlib.sha256(overlay).hexdigest(),'session':'Direct Plasma on framebuffer Xorg/Openbox; Qt xcb software; no KWin'},indent=2))
subprocess.run([sys.executable,str(p.parents[1]/'tools/make-op13-efi-media.py'),'--directory',str(media),'--output',str(p/'armada-ram-v2.img'),'--size-mib','1952'],check=True)
check=subprocess.run(['/sbin/fsck_msdos','-n',str(p/'armada-ram-v2.img')],capture_output=True,text=True);(p/'v2-fat-check.txt').write_text(check.stdout+check.stderr);check.check_returncode()
with (p/'armada-ram-v2.img').open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
result=json.loads((p/'BUILD.json').read_text());result.update(media_sha256=digest,media='armada-ram-v2.img',session='Direct Armada Plasma on framebuffer Xorg/Openbox, Qt xcb software rendering',boot_confirmed=False,desktop_confirmed=False,uefi='project-boot/dodge-uefi.img')
(p/'BUILD-v2.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
