#!/usr/bin/env python3
"""Append matching USB drivers/control service to the prepared Armada X11 image."""
from pathlib import Path
import gzip,hashlib,json,math,os,stat,subprocess,sys
p=Path(__file__).resolve().parent;project=p.parents[1];armada=p.parent/'armada-ram-v1';media=armada/'media';marker=p/'overlay.json'
basebytes=json.loads(marker.read_text())['base_initrd_bytes'] if marker.exists() else (media/'INITRD').stat().st_size
with (media/'INITRD').open('r+b') as raw:
 raw.truncate(basebytes);raw.seek(basebytes)
 with gzip.GzipFile(fileobj=raw,mode='wb',compresslevel=6,mtime=0) as dst:
  ino=1;offset=0
  def emit(data):
   global offset
   dst.write(data);offset+=len(data)
  def add(name,mode,data=b''):
   global ino
   n=name.encode()+b'\0';v=[ino,mode,0,0,1,0,len(data),0,0,0,0,len(n),0]
   emit(b'070701'+b''.join(f'{x:08x}'.encode() for x in v)+n);emit(b'\0'*(-offset%4));emit(data);emit(b'\0'*(-offset%4));ino+=1
  add('usb-modules',stat.S_IFDIR|0o755)
  for f in (p/'module-root').glob('*.ko'):add('usb-modules/'+f.name,stat.S_IFREG|0o644,f.read_bytes())
  for name in ['usb-startup.sh','usb-control.py']:add(name,stat.S_IFREG|0o755,(p/name).read_bytes())
  host=(p.parent/'arch-gnome-touch-v1/session/boot-shell.sh').read_text().replace('GNOME','Armada').replace('/gnome-session.sh','/host-session.sh').replace('bash /touch-usb.sh','bash /usb-startup.sh')
  add('boot-shell.sh',stat.S_IFREG|0o755,host.encode())
  info=(armada/'armada-info.sh').read_text().replace("exec /usr/bin/bash --noprofile --norc -i","printf '\\nUSB recovery status:\\n'; tail -25 /run/usb-startup.log\nexec /usr/bin/bash --noprofile --norc -i")
  add('armada/armada-info.sh',stat.S_IFREG|0o755,info.encode());add('TRAILER!!!',0)
subprocess.run(['/bin/bash','-n',str(p/'usb-startup.sh')],check=True)
(media/'OP13.DTB').write_bytes((p/'OP13-USB.DTB').read_bytes())
size=math.ceil((sum(f.stat().st_size for f in media.rglob('*') if f.is_file())+32*2**20)/(16*2**20))*16;assert size<=2047,size
subprocess.run([sys.executable,str(project/'tools/make-op13-efi-media.py'),'--directory',str(media),'--output',str(p/'armada-usb.img'),'--size-mib',str(size)],check=True)
check=subprocess.run(['/sbin/fsck_msdos','-n',str(p/'armada-usb.img')],capture_output=True,text=True);(p/'fat-check.txt').write_text(check.stdout+check.stderr);check.check_returncode()
with (p/'armada-usb.img').open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
result={'base_initrd_bytes':basebytes,'media_sha256':digest,'size_mib':size,'phone_storage_writes':False,'usb_runtime_verified':False,'desktop_runtime_verified':False,'kernel':'7.3.0-1-aarch64-ARCH','session':'Armada userspace, Plasma/KWin X11 6.7.5 compatibility, USB2 fixed-command CDC recovery'}
marker.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
