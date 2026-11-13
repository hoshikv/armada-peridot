#!/usr/bin/env python3
"""Build an isolated RAM image without changing the working Armada media."""
from pathlib import Path
import gzip,hashlib,json,math,shutil,stat,subprocess,sys,time,os
p=Path(__file__).resolve().parent;root=p.parents[1]
native=p.parent/'armada-native-v1'
fastfetch=p.parent/'armada-fastfetch-v1'
hardware=p.parent/'armada-hardware-v1'
wayland=p.parent/'armada-wayland-v1'
thermal=p.parent/'armada-thermal-v1' if os.environ.get('OP13_THERMAL_BUILD')=='1' else None
out=thermal or p
base=p.parent/'armada-ram-v1/media';media=out/'media'
media.mkdir(exist_ok=True)
initrd=media/'INITRD'
if initrd.exists():initrd.unlink()
if not (p/'BASE-STEAM.INITRD').exists():
 subprocess.run([sys.executable,str(p/'prepare-base.py')],check=True)
subprocess.run(['cp','-c',str(p/'BASE-STEAM.INITRD'),str(initrd)],check=True)

(media/'EFI/LINUX').mkdir(parents=True,exist_ok=True)
shutil.copyfile(base/'EFI/LINUX/BOOTAA64.EFI',media/'EFI/LINUX/BOOTAA64.EFI')
shutil.copyfile(thermal/'OP13-THERMAL.DTB' if thermal else hardware/'OP13-HARDWARE.DTB',media/'OP13.DTB')
(media/'LINUX.CFG').write_text((base/'LINUX.CFG').read_text().strip().replace(' nomodeset','').replace(' maxcpus=1','')+(' maxcpus=1 cpufreq.default_governor=schedutil' if thermal else '')+' deferred_probe_timeout=180\n')
entries={}
def addfile(name,path,mode=0o644):entries[name]=(mode,Path(path).read_bytes())
for name in ['usb-control.py','native-startup.sh']:addfile(name,(p if (p/name).exists() else hardware)/name,0o755)
addfile('usr/bin/te-probe',native/'te-probe',0o755)
addfile('armada/usr/bin/gpu-render-test',native/'gpu-render-test',0o755)
for name in ['armada-session.sh','armada-desktop.sh','armada-info.sh']:
 addfile('armada/'+name,(p if (p/name).exists() else native)/name,0o755)
addfile('armada/native-network-startup.sh',native/'native-network-startup.sh',0o755)
for name in ['wpa_supplicant.conf','org.freedesktop.NetworkManager.conf']:
 addfile('usr/share/dbus-1/system.d/'+name,Path('/Volumes/DodgeGnomeBuild/armada-root/usr/share/dbus-1/system.d')/name)
boot=(p.parent/'arch-gnome-touch-v1/session/boot-shell.sh').read_text().replace('GNOME','Armada').replace('/gnome-session.sh','/host-session.sh').replace('bash /touch-usb.sh','bash /usb-startup.sh')
boot=boot.replace('dbus-uuidgen --ensure=/etc/machine-id', 'if [[ ! -s /etc/machine-id ]]; then rm -f /etc/machine-id; fi\ndbus-uuidgen --ensure=/etc/machine-id\ncp /etc/machine-id /run/op13-machine-id')
boot=boot[:boot.index("printf '\\nArch Armada RAM boot: starting framebuffer Xorg.")]+"\nfor ((i=0;i<90;i++)); do [[ -e /run/native-ready ]] && break; sleep 1; done\nbash /host-session.sh >/run/armada-session.log 2>&1\nexec /usr/bin/bash --noprofile --norc -i\n"
boot=boot.replace('export LANG=C.UTF-8', 'python -c \"import time; time.clock_settime(time.CLOCK_REALTIME, '+str(int(time.time()))+')\"\nexport LANG=C.UTF-8',1)
entries['boot-shell.sh']=(0o755,boot.encode())
addfile('hardware-modules/fuse.ko',p/'fuse.ko')
addfile('host-session.sh',p/'host-session.sh',0o755)
package=fastfetch/'package/fastfetch-linux-aarch64'
for f in package.rglob('*'):
 if f.is_file():
  assert not f.is_symlink(),f
  addfile('armada/'+str(f.relative_to(package)),f,0o755 if str(f.relative_to(package)).startswith('usr/bin/') else 0o644)
for name in ['load-modules.sh','buttons.py']:addfile(name,(p if (p/name).exists() else hardware)/name,0o755)
addfile('armada/bluetooth-startup.sh',hardware/'bluetooth-startup.sh',0o755)
addfile('usr/share/dbus-1/system.d/bluetooth.conf','/Volumes/DodgeGnomeBuild/armada-root/usr/share/dbus-1/system.d/bluetooth.conf')
for f in (hardware/'modules').glob('*.ko'):addfile('hardware-modules/'+f.name,f)
for name in ['gngbtfw20.mbn','gngbtnv20.bin']:addfile('usr/lib/firmware/qca/'+name,p.parent/'armada-ram-v1/source/system_files/usr/lib/firmware/qca'/name)
entries['armada/etc/udev/rules.d/99-op13-ram-touch.rules']=(0o644,b'SUBSYSTEM=="input", KERNEL=="event*", ATTRS{name}=="OnePlus13 S3910 RAM touch", ENV{ID_INPUT}="1", ENV{ID_INPUT_TOUCHSCREEN}="1", ENV{WL_OUTPUT}="DSI-1"\n')
for f in (p.parent/'arch-usb-control-v1/module-root').glob('*.ko'):addfile('usb-modules/'+f.name,f)
for name in ['dispcc-sm8750','panel-aa569-p-3-a0019-dsc']:addfile('native-modules/'+name+'.ko',Path('/Volumes/DodgeGnomeBuild/wayland-modules')/(name+'.ko'))
usb=(p.parent/'arch-usb-control-v1/usb-startup.sh').read_text()+'\nbash /native-startup.sh &\n'
entries['usb-startup.sh']=(0o755,usb.encode())
for name in ['gpucc-sm8750','gxclkctl-kaanapali','pwrseq-qcom-wcn','pci-pwrctrl-pwrseq']:
 addfile('native-modules/'+name+'.ko',Path('/Volumes/DodgeGnomeBuild/native-modules')/(name+'.ko'))
addfile('native-modules/msm.ko',hardware/'msm-wake.ko')
for name in ['ath12k','wifi7/ath12k_wifi7']:
 addfile('native-modules/'+Path(name).name+'.ko',Path('/Volumes/DodgeGnomeBuild/usb-linux-source/linux-7.3/drivers/net/wireless/ath/ath12k')/(name+'.ko'))
for name in ['drm_exec','drm_gpuvm','gpu-sched','drm_client_lib','mdt_loader','ocmem','ubwc_config','rfkill','cfg80211','libarc4','mac80211','qmi_helpers','mhi','qrtr','qrtr-mhi']:
 addfile('native-modules/'+name+'.ko',native/'stock-modules'/(name+'.ko'))
fw=p.parent/'wifi/darwin-station-v14/root/fw'
for name in ['gen80000_sqe.fw','gen80000_aqe.fw','gen80000_gmu.bin']:
 addfile('usr/lib/firmware/qcom/'+name,fw/name)
addfile('usr/lib/firmware/qcom/sm8750/oneplus/dodge/gen80000_zap.mbn',fw/'gen80000_zap.mbn')
wifi=root/'diagnostics/20261025-wifi/firmware/peach'
for dest,source in [('amss.bin',wifi/'amss20.bin'),('board.bin',wifi/'bdwlan.elf'),('regdb.bin',wifi/'regdb.bin'),('m3.bin',root/'diagnostics/20261029-wifi/native-reference/mounted-phy_ucode20.elf'),('aux_ucode.bin',root/'diagnostics/20261029-wifi/native-reference/mounted-aux_ucode20.elf')]:
 addfile('usr/lib/firmware/ath12k/WCN7860/hw2.0/'+dest,source)
addfile('usr/lib/firmware/ath12k/WCN7860/hw2.0/qdss.cfg',root/'diagnostics/20261029-wifi/native-reference/mounted-qdss_trace_config_v2.cfg')
for f in [p/'usb-control.py',p/'control-phone.py']:compile(f.read_text(),str(f),'exec')
subprocess.run(['/bin/bash','-n',str(p/'native-startup.sh')],check=True)
# Add native Steam client files and symlinks; the x86 game runtimes are omitted.
symlinks={}
steamroot=Path('/Volumes/DodgeGnomeBuild/steam-extra')
for path in steamroot.rglob('*'):
 name='armada/'+str(path.relative_to(steamroot))
 if path.is_symlink():symlinks[name]=str(path.readlink()).encode()
 elif path.is_file():addfile(name,path,path.stat().st_mode & 0o777)
for name in ['steam-session.sh','steam-prepare.sh','steam-launch.sh']:addfile('armada/'+name,p/name,0o755)
entries['armada/usr/share/applications/steam.desktop']=(0o644,b'[Desktop Entry]\nType=Application\nName=Steam Big Picture\nExec=/usr/bin/bash /steam-launch.sh\nIcon=steam\nTerminal=false\nCategories=Game;\n')
entries['armada/var/roothome/Desktop/Steam Big Picture.desktop']=(0o755,entries['armada/usr/share/applications/steam.desktop'][1])
if thermal:
 for f in (thermal/'modules').glob('*.ko'):addfile('thermal-modules/'+f.name,f)
 for name in ['thermal-guard.py','thermal-watchdog.py','thermal-test.py']:addfile(name,thermal/name,0o755)
 # Recovery USB is online before thermal initialization; no GUI load until ready.
 usb=(p.parent/'arch-usb-control-v1/usb-startup.sh').read_text()+"\npython /thermal-guard.py >/run/thermal-guard.log 2>&1 &\npython /thermal-watchdog.py >/run/thermal-watchdog.log 2>&1 &\nfor ((i=0;i<90;i++)); do [[ -e /run/thermal-ready ]] && break; sleep 1; done\n[[ -e /run/thermal-ready ]] && bash /native-startup.sh &\n"
 entries['usb-startup.sh']=(0o755,usb.encode())
 boot=entries['boot-shell.sh'][1].decode().replace('bash /host-session.sh >', 'while [[ ! -e /run/thermal-ready ]]; do sleep 1; done\nbash /host-session.sh >')
 entries['boot-shell.sh']=(0o755,boot.encode())
 control=entries['usb-control.py'][1].decode().replace("['steam-prepare','steam-session'", "['thermal-guard','thermal-watchdog','steam-prepare','steam-session'")
 control=control.replace(" elif cmd==b'CPUSTATUS':", " elif cmd==b'THERMALSTATUS':reply(fd,'THERMALSTATUS',json.dumps({'state':json.loads(Path('/run/thermal-state.json').read_text()),'failure':Path('/run/thermal-failure.json').read_text() if Path('/run/thermal-failure.json').exists() else None}).encode())\n elif cmd==b'CPUSTATUS':")
 control=control.replace(" elif cmd==b'CPUSTATUS':", " elif cmd==b'THERMALTEST':reply(fd,'THERMALTEST',subprocess.run(['/usr/bin/python','/thermal-test.py'],capture_output=True,check=True,timeout=15).stdout)\n elif cmd==b'CPUSTATUS':")
 control=control.replace('def steamstart(software=False):', "def steamstart(software=False):\n state=json.loads(Path('/run/thermal-state.json').read_text())\n assert state['phase']=='ready' and time.monotonic()-state['monotonic']<3,'Thermal control is not healthy'")
 entries['usb-control.py']=(0o755,control.encode())
 # Every launcher, including direct desktop activation, checks the heartbeat.
 prepare=entries['armada/steam-prepare.sh'][1].decode().replace('mkdir -p /var/home', "python3 -c \"import json,time; s=json.load(open('/run/thermal-state.json')); assert s['phase']=='ready' and time.monotonic()-s['monotonic']<3\" || exit 1\nmkdir -p /var/home",1)
 entries['armada/steam-prepare.sh']=(0o755,prepare.encode())
 for script in ['steam-session.sh','steam-launch.sh']:
  content=entries['armada/'+script][1].decode().replace('exec >>/run/', "python3 -c \"import json,time; s=json.load(open('/run/thermal-state.json')); assert s['phase']=='ready' and time.monotonic()-s['monotonic']<3\" || exit 1\nexec >>/run/",1) if script=='steam-launch.sh' else entries['armada/'+script][1].decode().replace('export HOME=', "python3 -c \"import json,time; s=json.load(open('/run/thermal-state.json')); assert s['phase']=='ready' and time.monotonic()-s['monotonic']<3\" || exit 1\nexport HOME=",1)
  entries['armada/'+script]=(0o755,content.encode())
 for name,(mode,data) in entries.items():
  if name.endswith('.py') and not name.startswith('armada/var/home/'):compile(data,name,'exec')
  if name.endswith('.sh') and not name.startswith('armada/var/home/'):
   r=subprocess.run(['/bin/bash','-n'],input=data,capture_output=True);assert not r.returncode,(name,r.stderr)
dirs=set()
for name in list(entries)+list(symlinks):
 for parent in Path(name).parents:
  if str(parent)!='.':dirs.add(str(parent))
with initrd.open('ab') as raw,gzip.GzipFile(fileobj=raw,mode='wb',compresslevel=6,mtime=0) as dst:
 offset=0;ino=1
 def emit(data):
  global offset
  dst.write(data);offset+=len(data)
 def add(name,mode,data=b''):
  global ino
  n=name.encode()+b'\0';fields=[ino,mode,0,0,1,0,len(data),0,0,0,0,len(n),0]
  emit(b'070701'+b''.join(f'{v:08x}'.encode() for v in fields)+n);emit(b'\0'*(-offset%4));emit(data);emit(b'\0'*(-offset%4));ino+=1
 for name in sorted(dirs,key=lambda x:(x.count('/'),x)):add(name,stat.S_IFDIR|0o755)
 for name,(mode,data) in sorted(entries.items()):add(name,stat.S_IFREG|mode,data)
 for name,data in sorted(symlinks.items()):add(name,stat.S_IFLNK|0o777,data)
 add('TRAILER!!!',0)
size=math.ceil((sum(f.stat().st_size for f in media.rglob('*') if f.is_file())+8*2**20)/(8*2**20))*8
assert size<=2047,size
image=out/('armada-thermal.img' if thermal else 'armada-steam.img')
subprocess.run([sys.executable,str(root/'tools/make-op13-efi-media.py'),'--directory',str(media),'--output',str(image),'--size-mib',str(size)],check=True)
r=subprocess.run(['/sbin/fsck_msdos','-n',str(image)],capture_output=True,text=True)
(out/'fat-check.txt').write_text(r.stdout+r.stderr);r.check_returncode()
with image.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
result={'media_sha256':sha,'size_mib':size,'phone_storage_writes':False,'native_display_enabled':True,'gpu_max_hz':222000000,'runtime_verified':False,'wifi_enabled':True,'purpose':'Native ARM Steam Big Picture UI test; KDE Wayland150%, Bluetooth/buttons retained; no game runtime'}
if thermal:result.update({'purpose':'Thermal-controlled RAM test with native Steam UI','thermal_runtime_verified':False,'cpu_max_target_khz':1500000,'cpu_boot_online':1,'cpu_runtime_online_target':8,'thermal_throttle_millicelsius':[70000,80000],'thermal_reboot_millicelsius':85000})
(out/'BUILD.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
