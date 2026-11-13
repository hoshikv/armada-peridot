#!/usr/bin/env python3
"""Build an isolated RAM image without changing the working Armada media."""
from pathlib import Path
import gzip,hashlib,json,math,shutil,stat,subprocess,sys
p=Path(__file__).resolve().parent;root=p.parents[1]
native=p.parent/'armada-native-v1'
base=p.parent/'armada-ram-v1/media';media=p/'media'
media.mkdir(exist_ok=True)
initrd=media/'INITRD'
if initrd.exists():initrd.unlink()
subprocess.run(['cp','-c',str(base/'INITRD'),str(initrd)],check=True)
with initrd.open('r+b') as f:f.truncate(json.loads((p.parent/'armada-ram-v1/retry-overlay.json').read_text())['base_initrd_bytes'])
(media/'EFI/LINUX').mkdir(parents=True,exist_ok=True)
shutil.copyfile(base/'EFI/LINUX/BOOTAA64.EFI',media/'EFI/LINUX/BOOTAA64.EFI')
shutil.copyfile(p/'OP13-WAYLAND.DTB',media/'OP13.DTB')
(media/'LINUX.CFG').write_text((base/'LINUX.CFG').read_text().strip().replace(' nomodeset','')+' deferred_probe_timeout=180\n')
entries={}
def addfile(name,path,mode=0o644):entries[name]=(mode,Path(path).read_bytes())
for name in ['usb-control.py','native-startup.sh']:addfile(name,p/name,0o755)
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
entries['boot-shell.sh']=(0o755,boot.encode())
addfile('host-session.sh',p/'host-session.sh',0o755)
entries['armada/etc/udev/rules.d/99-op13-ram-touch.rules']=(0o644,b'SUBSYSTEM=="input", KERNEL=="event*", ATTRS{name}=="OnePlus13 S3910 RAM touch", ENV{ID_INPUT}="1", ENV{ID_INPUT_TOUCHSCREEN}="1", ENV{WL_OUTPUT}="DSI-1"\n')
for f in (p.parent/'arch-usb-control-v1/module-root').glob('*.ko'):addfile('usb-modules/'+f.name,f)
for name in ['dispcc-sm8750','panel-aa569-p-3-a0019-dsc']:addfile('native-modules/'+name+'.ko',Path('/Volumes/DodgeGnomeBuild/wayland-modules')/(name+'.ko'))
usb=(p.parent/'arch-usb-control-v1/usb-startup.sh').read_text()+'\nbash /native-startup.sh &\n'
entries['usb-startup.sh']=(0o755,usb.encode())
for name in ['gpucc-sm8750','gxclkctl-kaanapali','pwrseq-qcom-wcn','pci-pwrctrl-pwrseq']:
 addfile('native-modules/'+name+'.ko',Path('/Volumes/DodgeGnomeBuild/native-modules')/(name+'.ko'))
addfile('native-modules/msm.ko',p/'msm.ko')
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
dirs=set()
for name in entries:
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
 add('TRAILER!!!',0)
size=math.ceil((sum(f.stat().st_size for f in media.rglob('*') if f.is_file())+32*2**20)/(16*2**20))*16
assert size<=2047,size
image=p/'armada-wayland.img'
subprocess.run([sys.executable,str(root/'tools/make-op13-efi-media.py'),'--directory',str(media),'--output',str(image),'--size-mib',str(size)],check=True)
r=subprocess.run(['/sbin/fsck_msdos','-n',str(image)],capture_output=True,text=True)
(p/'fat-check.txt').write_text(r.stdout+r.stderr);r.check_returncode()
with image.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
result={'media_sha256':sha,'size_mib':size,'phone_storage_writes':False,'native_display_enabled':True,'gpu_max_hz':222000000,'runtime_verified':False,'wifi_enabled':True,'purpose':'Native OnePlus 13 DRM Wayland RAM experiment'}
(p/'BUILD.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
