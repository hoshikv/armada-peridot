#!/usr/bin/env python3
"""Combine tested RAM framebuffer/touch host with official Armada desktop root."""
from pathlib import Path
import gzip,hashlib,json,math,os,shutil,stat,struct,subprocess
p=Path(__file__).resolve().parent;r=p/'root';base=p.parent/'arch-gnome-v1';touch=p.parent/'arch-gnome-touch-v1'
for d in ['dev','proc','sys','run','tmp','var/roothome','var/home','var/lib/dbus','var/cache','etc/xdg','etc/skel']:(r/d).mkdir(exist_ok=True,parents=True)
if not (r/'root').exists():(r/'root').symlink_to('var/roothome')
for name in ['armada-session.sh','armada-desktop.sh','armada-info.sh']:
 subprocess.run(['/bin/bash','-n',str(p/name)],check=True)
 shutil.copyfile(p/name,r/name);(r/name).chmod(0o755)
# No system or user update/install services are started. Disable desktop automount.
config=r/'var/roothome/.config';config.mkdir(parents=True,exist_ok=True)
(config/'kded6rc').write_text('[Module-device_automounter]\nautoload=false\n[Module-automounter]\nautoload=false\n')
(config/'plasmarc').write_text('[Theme]\nname=breeze-dark\n')
for d in ['usr/share/dbus-1/system-services','usr/share/dbus-1/services']:
 for f in (r/d).glob('*'):
  if any(n in f.name.lower() for n in ['udisks','fwupd','packagekit','bootupd']):f.unlink()
for f in (r/'etc/xdg/autostart').glob('*'):f.unlink()
for name in ['usr/libexec/armada/armada-installer','usr/bin/armada-bootimg-update','usr/bin/armada-rebase']:
 f=r/name
 if f.is_file() or f.is_symlink():f.unlink()
# Check dynamic dependencies against the Armada root, including loaded Qt/KWin plugins.
def needed(f):
 b=f.read_bytes()
 if b[:5]!=b'\x7fELF\x02':return []
 assert struct.unpack_from('<H',b,18)[0]==183, f
 off=struct.unpack_from('<Q',b,40)[0];size,n=struct.unpack_from('<HH',b,58)
 if not off:return []
 ss=[struct.unpack_from('<IIQQQQIIQQ',b,off+i*size) for i in range(n)];out=[]
 for s in ss:
  if s[1]!=6:continue
  st=ss[s[6]];names=b[st[4]:st[4]+st[5]]
  for o in range(s[4],s[4]+s[5],16):
   tag,v=struct.unpack_from('<QQ',b,o)
   if tag==1:out.append(names[v:names.index(b'\0',v)].decode())
 return out
libdirs=[r/d for d in ['usr/lib64','usr/lib','usr/lib64/pulseaudio','usr/lib64/systemd','usr/lib64/samba','usr/lib64/libproxy','usr/lib64/qt6/libexec','usr/lib64/qt6/lib']]
# Browser, VPN setup and printer plugins belong to omitted optional packages.
for name in ['usr/lib64/qt6/plugins/webview/libqtwebview_webengine.so','usr/lib64/qt6/plugins/printsupport/libcupsprintersupport.so','usr/lib64/qt6/plugins/plasma/network/vpn/plasmanetworkmanagement_openconnect_arrayui.so']:
 f=r/name
 if f.exists():f.unlink()
pending=[r/'usr/bin'/name for name in ['bash','dbus-run-session','dbus-daemon','kwin_wayland','plasmashell','konsole','kded6','kbuildsycoca6','fc-cache']]
plugins=[f for d in ['usr/lib64/qt6/plugins','usr/lib64/qt6/qml','usr/lib64/dri'] for f in (r/d).rglob('*.so') if f.is_file()]
for f in plugins:
 deps=needed(f)
 if any(lib.startswith('libQt6WebEngine') or lib=='libcups.so.2' for lib in deps):
  f.unlink()
 else:pending.append(f)
seen=set();missing={}
while pending:
 f=pending.pop()
 if f in seen:continue
 seen.add(f)
 if not f.exists():missing[str(f)]='file absent';continue
 for lib in needed(f):
  dep=next((d/lib for d in [f.parent,*libdirs] if (d/lib).exists()),None)
  if dep is None:missing[lib]=str(f.relative_to(r))
  else:pending.append(dep)
(p/'dependency-check.json').write_text(json.dumps({'checked':len(seen),'missing':missing},indent=2))
if missing:raise RuntimeError('Missing Armada dependencies: '+str(missing))
print('Armada dynamic closure passed:',len(seen),flush=True)
media=p/'media';(media/'EFI/LINUX').mkdir(exist_ok=True,parents=True)
print('Pruning unused GNOME assets from framebuffer host...',flush=True)
drop=('usr/share/locale/','usr/share/ibus/','usr/share/gir-1.0/','usr/share/backgrounds/','usr/lib/gnome-shell/','usr/lib/mutter-51/','usr/lib/libwebkitgtk','usr/lib/libjavascriptcoregtk','usr/lib/libmozjs')
with gzip.open(base/'media/INITRD','rb') as src,gzip.GzipFile(filename=str(media/'INITRD'),mode='wb',compresslevel=3,mtime=0) as dst:
 while True:
  header=src.read(110)
  if not header:break
  assert header[:6]==b'070701'
  fields=[int(header[6+i*8:14+i*8],16) for i in range(13)]
  namesz=fields[11];filesz=fields[6];name=src.read(namesz);npad=src.read(-(110+namesz)%4)
  data=src.read(filesz);dpad=src.read(-filesz%4)
  if not name[:-1].decode().startswith(drop):dst.write(header+name+npad+data+dpad)
  if name==b'TRAILER!!!\0':break
with (media/'INITRD').open('ab') as raw:
 raw.write((touch/'touch-overlay.gz').read_bytes())
 with gzip.GzipFile(fileobj=raw,mode='wb',compresslevel=3,mtime=0) as archive:
  ino=1;offset=0
  def emit(b):
   global offset
   archive.write(b);offset+=len(b)
  def add(name,mode,data=b'',file=None):
   global ino
   n=name.encode()+b'\0';size=file.stat().st_size if file else len(data)
   fields=[ino,mode,0,0,1,0,size,0,0,0,0,len(n),0]
   emit(b'070701'+b''.join(f'{v:08x}'.encode() for v in fields)+n);emit(b'\0'*(-offset%4))
   if file:
    with file.open('rb') as src:
     while chunk:=src.read(1024*1024):emit(chunk)
   else:emit(data)
   emit(b'\0'*(-offset%4));ino+=1
  add('armada',stat.S_IFDIR|0o755)
  print('Compressing Armada RAM overlay...',flush=True)
  for f in sorted(r.rglob('*')):
   name='armada/'+f.relative_to(r).as_posix();mode=f.lstat().st_mode
   if f.is_symlink():add(name,stat.S_IFLNK|0o777,os.readlink(f).encode())
   elif f.is_dir():add(name,stat.S_IFDIR|(mode&0o7777))
   elif f.is_file():add(name,stat.S_IFREG|(mode&0o777),file=f)
  host=(touch/'session/boot-shell.sh').read_text().replace('GNOME','Armada').replace('/gnome-session.sh','/host-session.sh')
  add('boot-shell.sh',stat.S_IFREG|0o755,host.encode())
  add('host-session.sh',stat.S_IFREG|0o755,(p/'host-session.sh').read_bytes())
  add('TRAILER!!!',0)
  print('Armada overlay uncompressed MiB',round(offset/2**20,1),flush=True)
shutil.copyfile(touch/'media/EFI/LINUX/BOOTAA64.EFI',media/'EFI/LINUX/BOOTAA64.EFI')
shutil.copyfile(touch/'OP13.DTB',media/'OP13.DTB')
shutil.copyfile(touch/'media/LINUX.CFG',media/'LINUX.CFG')
size=math.ceil((sum(f.stat().st_size for f in media.rglob('*') if f.is_file())+64*2**20)/(16*2**20))*16
assert size<=2047,(size,'exceeds RAM loader limit')
print('FAT RAM media MiB',size,flush=True)
subprocess.run(['/opt/homebrew/bin/python3',str(p.parents[1]/'tools/make-op13-efi-media.py'),'--directory',str(media),'--output',str(p/'armada-ram.img'),'--size-mib',str(size)],check=True)
res=subprocess.run(['/sbin/fsck_msdos','-n',str(p/'armada-ram.img')],capture_output=True,text=True);(p/'fat-check.txt').write_text(res.stdout+res.stderr);res.check_returncode()
with (p/'armada-ram.img').open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
(p/'BUILD.json').write_text(json.dumps({'media_sha256':digest,'size_mib':size,'armada_version':'20261109.dfed5d6','upstream_manifest_digest':'sha256:0f0c990818303ae621c7bcbd10979409aa1143a12e2457f3c0c0452652d35d73','official_blob_sha256_verified':True,'signature_verified':False,'boot_confirmed':False,'desktop_confirmed':False,'steam_proton_fex_included':False,'phone_storage_writes':False,'session':'Experimental Armada KDE userspace nested on tested Arch framebuffer host; software rendering'},indent=2))
print('Armada RAM image prepared.',flush=True)
