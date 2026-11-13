#!/usr/bin/env python3
"""Extract a reduced official Armada desktop userspace for a RAM-only test."""
import concurrent.futures,hashlib,json,os,pathlib,tarfile,time,urllib.request
p=pathlib.Path(__file__).resolve().parent
r=pathlib.Path('/Volumes/DodgeGnomeBuild/armada-root');r.mkdir(exist_ok=True)
(p/'root').symlink_to(r) if not (p/'root').exists() else None
m=json.loads((p/'manifest.json').read_text())
skip={0,1,2,3,5,6,7,8,9,15,16,17,18,19,25,28,31,34,38,39,43,44,46,47,48,49,59,60,63,64,65,67,70,76,79,84,85,87,89}
selected=[(i,l) for i,l in enumerate(m['layers']) if i not in skip]
(p/'selection.json').write_text(json.dumps({'included':[i for i,l in selected],'excluded':sorted(skip),'steam_proton_fex_included':False,'version':'20261109.dfed5d6'},indent=2))
token=json.load(urllib.request.urlopen('https://ghcr.io/token?service=ghcr.io&scope=repository:armada-os/armada:pull',timeout=30))['token']
(p/'blobs').mkdir(exist_ok=True)
def fetch(item):
 i,l=item;digest=l['digest'].split(':')[1];f=p/'blobs'/digest
 if f.exists() and f.stat().st_size==l['size'] and hashlib.file_digest(f.open('rb'),'sha256').hexdigest()==digest:return i,f
 for attempt in range(3):
  try:
   req=urllib.request.Request('https://ghcr.io/v2/armada-os/armada/blobs/'+l['digest'],headers={'Authorization':'Bearer '+token})
   h=hashlib.sha256()
   with urllib.request.urlopen(req,timeout=45) as src,f.with_suffix('.part').open('wb') as dst:
    while b:=src.read(1024*1024):dst.write(b);h.update(b)
   assert h.hexdigest()==digest
   assert f.with_suffix('.part').stat().st_size==l['size']
   f.with_suffix('.part').rename(f)
   print('Downloaded',i,round(l['size']/1e6,1),'MB',flush=True);return i,f
  except Exception:
   if attempt==2:raise
   time.sleep(2)
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:files=dict(ex.map(fetch,selected))
def allowed(n):
 if n.startswith(('usr/lib/firmware/','usr/lib/modules/','usr/share/doc/','usr/share/man/','usr/share/locale/','usr/include/','usr/src/','usr/share/rpm/','var/','boot/','sysroot/','ostree/','usr/lib/ostree/','usr/lib/bootc/')):return False
 return True
def filt(member,dest):
 if member.issym() and member.linkname.startswith('/'):
  member=member.replace(linkname=os.path.relpath(member.linkname.lstrip('/'),os.path.dirname(member.name)))
 return tarfile.data_filter(member,dest)
for i,l in selected:
 with tarfile.open(files[i]) as t:
  members=[x for x in t if allowed(x.name.removeprefix('./')) and not pathlib.PurePosixPath(x.name).name.startswith('.wh.') and not x.isdev()]
  t.extractall(r,members=members,filter=filt)
 print('Extracted',i,flush=True)
print('Armada desktop root extracted; not yet booted.',flush=True)
