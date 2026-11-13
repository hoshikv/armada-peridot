#!/usr/bin/env python3
"""Append a touch-only RAM overlay to the confirmed GNOME boot environment."""
from pathlib import Path
import gzip,hashlib,json,shutil,stat,subprocess,struct,sys
p=Path(__file__).resolve().parent;base=p.parent/'arch-gnome-v1';media=p/'media';(media/'EFI/LINUX').mkdir(parents=True,exist_ok=True)
entries={}
for f in (p/'session').glob('*.sh'):entries[f.name]=(0o755,f.read_bytes())
for name in ['touch-usb.sh','show-touch.sh','touch-input.py']:entries[name]=(0o755,(p/name).read_bytes())
entries['usr/bin/op13-touch']=(0o755,(p/'op13-touch').read_bytes())
for f in (p/'module-root').rglob('*'):
    if f.is_file():entries[f.relative_to(p/'module-root').as_posix()]=(0o644,f.read_bytes())
for name in ['touch-usb.sh','show-touch.sh']:
    subprocess.run(['/bin/bash','-n',str(p/name)],check=True)
for f in (p/'session').glob('*.sh'):subprocess.run(['/bin/bash','-n',str(f)],check=True)
compile((p/'touch-input.py').read_text(),'touch-input.py','exec')
cpio=bytearray();ino=1
def add(name,mode,data=b''):
    global ino
    name=name.encode()+b'\0';fields=[ino,mode,0,0,1,0,len(data),0,0,0,0,len(name),0]
    cpio.extend(b'070701'+b''.join(f'{v:08x}'.encode() for v in fields)+name)
    cpio.extend(b'\0'*(-len(cpio)%4));cpio.extend(data);cpio.extend(b'\0'*(-len(cpio)%4));ino+=1
directories=set()
for name in entries:
    parent=Path(name).parent
    while str(parent)!='.':directories.add(parent.as_posix());parent=parent.parent
for name in sorted(directories,key=lambda n:(n.count('/'),n)):add(name,stat.S_IFDIR|0o755)
for name,(mode,data) in sorted(entries.items()):add(name,stat.S_IFREG|mode,data)
add('TRAILER!!!',0)
overlay=gzip.compress(cpio,mtime=0);(p/'touch-overlay.gz').write_bytes(overlay)
shutil.copyfile(base/'media/INITRD',media/'INITRD')
with (media/'INITRD').open('ab') as f:f.write(overlay)
shutil.copyfile(base/'media/EFI/LINUX/BOOTAA64.EFI',media/'EFI/LINUX/BOOTAA64.EFI')
shutil.copyfile(p/'OP13.DTB',media/'OP13.DTB')
cmd=(base/'media/LINUX.CFG').read_text().strip()+' acpi=off op13_touch=1\n'
(media/'LINUX.CFG').write_text(cmd)
subprocess.run([sys.executable,str(p.parents[1]/'tools/make-op13-efi-media.py'),'--directory',str(media),'--output',str(p/'arch-gnome-touch.img'),'--size-mib','896'],check=True)
check=subprocess.run(['/sbin/fsck_msdos','-n',str(p/'arch-gnome-touch.img')],capture_output=True,text=True)
(p/'fat-check.txt').write_text(check.stdout+check.stderr);check.check_returncode()
def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
result=dict(media_sha256=sha(p/'arch-gnome-touch.img'),base_gnome_media_sha256=json.loads((base/'BUILD.json').read_text())['media_sha256'],driver_sha256=sha(p/'op13-touch'),fdt_sha256=sha(p/'OP13.DTB'),overlay_sha256=sha(p/'touch-overlay.gz'),media_size_mib=896,fat_check_passed=True,phone_storage_mounts_configured=False,phone_partition_writes=False,touch_hardware_confirmed=False,gnome_desktop_confirmed=False,cmdline=cmd)
(p/'BUILD.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
