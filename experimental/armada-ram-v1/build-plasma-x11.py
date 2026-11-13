#!/usr/bin/env python3
"""RAM-only compatibility overlay: Fedora Plasma/KWin X11 6.7.5."""
from pathlib import Path
import gzip,hashlib,json,math,os,stat,subprocess,sys
p=Path(__file__).resolve().parent;media=p/'media';root=p/'plasma-x11-root'
assert not json.loads((p/'plasma-x11-dependencies.json').read_text())['missing']
basebytes=json.loads((p/'retry-overlay.json').read_text())['base_initrd_bytes']
with (media/'INITRD').open('r+b') as raw:
 raw.truncate(basebytes);raw.seek(basebytes)
 with gzip.GzipFile(fileobj=raw,mode='wb',compresslevel=6,mtime=0) as dst:
  ino=1;offset=0
  def emit(data):
   global offset
   dst.write(data);offset+=len(data)
  def add(name,mode,data=b'',file=None):
   global ino
   n=name.encode()+b'\0';size=file.stat().st_size if file else len(data);v=[ino,mode,0,0,1,0,size,0,0,0,0,len(n),0]
   emit(b'070701'+b''.join(f'{x:08x}'.encode() for x in v)+n);emit(b'\0'*(-offset%4))
   if file:
    with file.open('rb') as src:
     while chunk:=src.read(1024*1024):emit(chunk)
   else:emit(data)
   emit(b'\0'*(-offset%4));ino+=1
  add('armada',stat.S_IFDIR|0o755)
  for f in sorted(root.rglob('*')):
   rel=f.relative_to(root).as_posix()
   if rel.startswith(('usr/share/doc/','usr/share/man/','usr/share/locale/')):continue
   name='armada/'+rel;mode=f.lstat().st_mode
   if f.is_symlink():add(name,stat.S_IFLNK|0o777,os.readlink(f).encode())
   elif f.is_dir():add(name,stat.S_IFDIR|(mode&0o7777))
   elif f.is_file():add(name,stat.S_IFREG|(mode&0o777),file=f)
  for f in p.glob('armada-*.sh'):
   subprocess.run(['/bin/bash','-n',str(f)],check=True);add('armada/'+f.name,stat.S_IFREG|0o755,f.read_bytes())
  add('host-session.sh',stat.S_IFREG|0o755,(p/'host-session.sh').read_bytes())
  add('TRAILER!!!',0)
size=math.ceil((sum(f.stat().st_size for f in media.rglob('*') if f.is_file())+32*2**20)/(16*2**20))*16
assert size<=2047,size
subprocess.run([sys.executable,str(p.parents[1]/'tools/make-op13-efi-media.py'),'--directory',str(media),'--output',str(p/'armada-ram-v3.img'),'--size-mib',str(size)],check=True)
check=subprocess.run(['/sbin/fsck_msdos','-n',str(p/'armada-ram-v3.img')],capture_output=True,text=True);(p/'v3-fat-check.txt').write_text(check.stdout+check.stderr);check.check_returncode()
with (p/'armada-ram-v3.img').open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
result=json.loads((p/'BUILD-v2.json').read_text());result.update(media_sha256=digest,media='armada-ram-v3.img',size_mib=size,session='Armada userspace with official Fedora Plasma/KWin X11 6.7.5 compatibility overlay, compositing disabled',boot_confirmed=False,desktop_confirmed=False)
(p/'BUILD-v3.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
