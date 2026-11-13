from pathlib import Path,PurePosixPath
import tarfile,json,collections,os
p=Path(__file__).resolve().parent;dest=Path('/Volumes/DodgeGnomeBuild/steam-extra');dest.mkdir(exist_ok=True)
prefix='var/home/armada/.local/share/Steam/';excluded=['steamapps/','compatibilitytools.d/','androidarm64/','ubuntu12_32/','ubuntu12_64/','linux32/','linux64/']
kept=[];skipped=collections.Counter()
with tarfile.open(p/'steam-layer.tar.gz','r|gz') as t:
 for m in t:
  name=m.name.removeprefix('./')
  if not name.startswith(prefix):continue
  rel=name[len(prefix):]
  skip=any(rel.startswith(x) for x in excluded) or (rel.startswith('package/') and ('.zip' in rel or rel.endswith('.tar.xz')))
  if skip:skipped[rel.split('/')[0]]+=m.size;continue
  assert '..' not in PurePosixPath(name).parts
  t.extract(m,dest,filter='data');kept.append({'path':name,'bytes':m.size,'mode':m.mode,'type':m.type.decode()})
steam=dest/'var/home/armada/.local/share/Steam';home=dest/'var/home/armada';(home/'.steam').mkdir(exist_ok=True)
for name,target in [('steam','../.local/share/Steam'),('root','../.local/share/Steam'),('sdkarm64','../.local/share/Steam/linuxarm64')]:
 f=home/'.steam'/name
 if not f.exists() and not f.is_symlink():f.symlink_to(target)
(p/'client-extraction.json').write_text(json.dumps({'destination':str(dest),'kept':kept,'skipped_bytes_by_group':skipped},indent=2)+'\n')
print('Extracted',len(kept),'entries,',sum(x['bytes'] for x in kept),'logical bytes. Skipped:',dict(skipped),flush=True)

# Complete the preparation used by the verified native ARM client build.
for link in json.loads((p/'soname-links.json').read_text()):
 path=steam/'steamrtarm64'/link['path']
 if not path.exists() and not path.is_symlink():path.symlink_to(link['target'])
wrapper=steam/'steamrtarm64/steamwebhelper.sh'
wrapper.write_text(wrapper.read_text().replace('exec taskset 0x7c ', 'exec '))
