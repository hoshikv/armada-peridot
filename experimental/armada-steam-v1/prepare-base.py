#!/usr/bin/env python3
"""Make room for native Steam by filtering only dispensable desktop-host assets.
Does not alter any verified image, source root, or phone storage.
"""
from pathlib import Path
import gzip,io,json
p=Path(__file__).resolve().parent;base=p.parent/'armada-ram-v1/media/INITRD'
limit=json.loads((p.parent/'armada-ram-v1/retry-overlay.json').read_text())['base_initrd_bytes']
class Limited(io.RawIOBase):
 def __init__(self,f,n):self.f=f;self.left=n
 def readable(self):return True
 def read(self,n=-1):
  if n<0:n=self.left
  b=self.f.read(min(n,self.left));self.left-=len(b);return b
# Arch host only runs USB recovery and the touchscreen bridge. Armada keeps
# its own graphics/Qt/Mesa libraries unchanged.
host=['usr/share/icons/','usr/share/themes/','usr/share/fonts/','usr/share/perl5/','usr/share/i18n/','usr/share/help/','usr/share/poppler/','usr/share/doc/','usr/share/gtk-doc/','usr/lib/perl5/','usr/lib/glycin-loaders/','usr/lib/gstreamer-1.0/','usr/lib/gnome-','usr/lib/mutter-','usr/lib/libLLVM','usr/lib/libgallium','usr/lib/libmozjs','usr/lib/libgtk-','usr/lib/libgdk-','usr/lib/libgs.','usr/lib/libavcodec','usr/lib/libavformat','usr/lib/libavfilter','usr/bin/js140','usr/bin/gtk4-','usr/bin/xgettext']
armada=['armada/usr/share/ibus/dicts/','armada/usr/share/speech-dispatcher/','armada/usr/share/espeak-ng-data/','armada/usr/share/help/','armada/usr/share/doc/']
removed=[];kept=0
out=p/'BASE-STEAM.INITRD'
with base.open('rb') as raw,out.open('wb') as dest,gzip.GzipFile(fileobj=Limited(raw,limit),mode='rb') as src,gzip.GzipFile(fileobj=dest,mode='wb',compresslevel=6,mtime=0) as dst:
 while True:
  h=src.read(110)
  if not h:break
  if h[:6]!=b'070701':raise ValueError(('Unexpected cpio header',h[:20]))
  fs=[int(h[6+i*8:14+i*8],16) for i in range(13)];n,size=fs[11],fs[6];name=src.read(n);pad=src.read(-(110+n)%4)
  path=name.rstrip(b'\0').decode().removeprefix('./');drop=any(path.startswith(prefix) for prefix in host+armada)
  if drop:removed.append({'path':path,'bytes':size})
  else:dst.write(h+name+pad);kept+=1
  left=size
  while left:
   b=src.read(min(left,2**20))
   if not b:raise EOFError(path)
   left-=len(b)
   if not drop:dst.write(b)
  pad=src.read(-size%4)
  if not drop:dst.write(pad)
(p/'base-filter.json').write_text(json.dumps({'removed':removed,'kept_entries':kept,'removed_logical_bytes':sum(x['bytes'] for x in removed),'output_bytes':out.stat().st_size,'phone_storage_writes':False},indent=2)+'\n')
print('Filtered host scratch base:',out.stat().st_size,'bytes;',len(removed),'optional entries removed',flush=True)
