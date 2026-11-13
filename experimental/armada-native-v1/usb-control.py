#!/usr/bin/python
"""Local USB CDC recovery protocol. Fixed read-only commands plus cold reboot."""
from pathlib import Path
import base64,ctypes,errno,json,os,select,subprocess,termios,time,uuid
LIMIT=32*1024*1024
def screenshot():
 fb=Path('/sys/class/graphics/fb0');w,h=map(int,(fb/'virtual_size').read_text().strip().split(','));stride=int((fb/'stride').read_text());bpp=int((fb/'bits_per_pixel').read_text())
 assert bpp==32 and 0<w<=8192 and 0<h<=8192 and w*4<=stride<=65536 and stride*h<=LIMIT
 with open('/dev/fb0','rb',buffering=0) as f:data=f.read(stride*h)
 assert len(data)==stride*h
 return data,{'width':w,'height':h,'stride':stride,'format':'BGRA8888'}
def status():
 return json.dumps({'identity':'OP13RAMCONTROL','kernel':os.uname().release,'usb':{p.name:(p/'state').read_text().strip() for p in Path('/sys/class/udc').glob('*')},'touch':Path('/run/touch-bridge.log').read_text()[-4000:] if Path('/run/touch-bridge.log').exists() else 'starting','phone_storage_mounts_configured':False}).encode()
def logs():
 out=bytearray()
 for name in ['usb-startup','native-startup','armada-gpu-glx','armada-gpu-desktop','armada-kwin-support','armada-kwin-restart','native-networkmanager','native-network-startup','op13-wpa','keyboard-test','Xorg.0','touch-bridge','armada-session','armada-kwin','armada-plasma','armada-konsole']:
  f=Path('/run/'+name+'.log')
  if f.exists():out.extend(('\n--- '+name+' ---\n').encode()+f.read_bytes()[-24000:])
 out.extend(b'\n--- dmesg ---\n'+subprocess.run(['/usr/bin/dmesg'],capture_output=True,timeout=5).stdout[-120000:])
 return bytes(out)
def hardware():
 out={}
 for name in ['/proc/modules','/proc/cmdline','/proc/mounts','/sys/kernel/debug/devices_deferred','/run/native-startup.log','/sys/kernel/debug/regulator/regulator_summary','/sys/kernel/debug/clk/clk_summary','/sys/kernel/debug/gpio']:
  try:out[name]=Path(name).read_text()[-32000:]
  except OSError as e:out[name]=str(e)
 for bus in ['pci','platform']:
  out[bus]=[]
  for dev in Path('/sys/bus/'+bus+'/devices').glob('*'):
   if bus=='platform' and not any(x in dev.name for x in ['3d','gpu','gmu','clock','pcie','phy','wcn','wifi']):continue
   d={'name':dev.name,'driver':str((dev/'driver').resolve()) if (dev/'driver').exists() else None}
   for field in ['vendor','device','class','modalias']:
    try:d[field]=(dev/field).read_text().strip()
    except OSError:pass
   out[bus].append(d)
 out['drm']=[str(n) for n in Path('/dev/dri').glob('*')]
 out['desktop_processes']=[]
 for proc in Path('/proc').glob('[0-9]*'):
  try:
   comm=(proc/'comm').read_text().strip()
   if any(x in comm.lower() for x in ['kwin','plasma','networkmanager','wpa','dbus']):out['desktop_processes'].append({'pid':proc.name,'comm':comm,'cmdline':(proc/'cmdline').read_bytes().replace(bytes([0]),b' ').decode(errors='replace')[:200]})
  except OSError:pass
 out['network_interfaces']=[n.name for n in Path('/sys/class/net').glob('*')]
 try:out['xrandr']=subprocess.run(['/usr/bin/xrandr','--verbose'],env={**os.environ,'DISPLAY':':0'},capture_output=True,text=True,timeout=8).stdout[-16000:]
 except Exception as e:out['xrandr']=str(e)
 return json.dumps(out,indent=2).encode()
def gpucheck():
 out={}
 env={k:v for k,v in os.environ.items() if k not in ['LIBGL_ALWAYS_SOFTWARE','GALLIUM_DRIVER','QT_QUICK_BACKEND','MESA_LOADER_DRIVER_OVERRIDE']}
 env.update({'EGL_PLATFORM':'surfaceless','XDG_RUNTIME_DIR':'/run/user/0','DISPLAY':':0','MESA_VK_WSI_DEBUG':'sw','VK_DRIVER_FILES':'/usr/share/vulkan/icd.d/freedreno_icd.aarch64.json'})
 for name,args in [('egl',['/usr/bin/eglinfo','-B','-p','surfaceless']),('vulkan',['/usr/bin/vulkaninfo','--summary']),('glx',['/usr/bin/glxinfo','-B'])]:
  try:
   r=subprocess.run(['/usr/bin/chroot','/armada']+args,env=env,capture_output=True,text=True,timeout=15)
   out[name]={'returncode':r.returncode,'stdout':r.stdout[-18000:],'stderr':r.stderr[-6000:]}
  except Exception as e:out[name]={'error':str(e)}
 zenv={**env,'GALLIUM_DRIVER':'zink','MESA_LOADER_DRIVER_OVERRIDE':'zink','LIBGL_KOPPER_DRI2':'true','MESA_VK_WSI_DEBUG':'sw','VK_DRIVER_FILES':'/usr/share/vulkan/icd.d/freedreno_icd.aarch64.json'}
 try:
  r=subprocess.run(['/usr/bin/chroot','/armada','/usr/bin/glxinfo','-B'],env=zenv,capture_output=True,text=True,timeout=15)
  out['glx_zink']={'returncode':r.returncode,'stdout':r.stdout[-12000:],'stderr':r.stderr[-6000:]}
 except Exception as e:out['glx_zink']={'error':str(e)}
 return json.dumps(out,indent=2).encode()
def retrygpu():
 # Only the three render-side devices; never rebind MDSS or a storage device.
 out={}
 for name in ['3da0000.iommu','3d37000.gmu','3d00000.gpu']:
  try:
   Path('/sys/bus/platform/drivers_probe').write_text(name)
   out[name]='probe requested'
  except OSError as e:out[name]=str(e)
 return json.dumps(out).encode()
def wificheck():
 if not list(Path('/sys/class/ieee80211').glob('*')):
  return json.dumps({'ready':False,'reason':'No wireless PHY registered'}).encode()
 env={**os.environ,'DBUS_SYSTEM_BUS_ADDRESS':'unix:path=/run/dbus/system_bus_socket'}
 startup=subprocess.run(['/usr/bin/chroot','/armada','/usr/bin/bash','/native-network-startup.sh'],env=env,capture_output=True,text=True,timeout=8)
 out={}
 for name,args in [('devices',['device','status']),('wifi',['device','wifi','list','--rescan','yes'])]:
  try:
   r=subprocess.run(['/usr/bin/chroot','/armada','/usr/bin/nmcli']+args,env=env,capture_output=True,text=True,timeout=12)
   out[name]={'returncode':r.returncode,'startup_returncode':startup.returncode,'startup_stderr':startup.stderr[-4000:],'stdout':r.stdout[-24000:],'stderr':r.stderr[-4000:]}
  except Exception as e:out[name]={'error':str(e)}
 return json.dumps(out).encode()
def rendertest():
 env={k:v for k,v in os.environ.items() if k not in ['LIBGL_ALWAYS_SOFTWARE','GALLIUM_DRIVER','MESA_LOADER_DRIVER_OVERRIDE']}
 env.update({'EGL_PLATFORM':'surfaceless','XDG_RUNTIME_DIR':'/run/user/0'})
 r=subprocess.run(['/usr/bin/chroot','/armada','/usr/bin/gpu-render-test'],env=env,capture_output=True,text=True,timeout=15)
 return json.dumps({'returncode':r.returncode,'stdout':r.stdout[-12000:],'stderr':r.stderr[-6000:]}).encode()
def desktopstatus():
 env={**os.environ,'DISPLAY':':0','QT_QPA_PLATFORM':'xcb'}
 for proc in Path('/proc').glob('[0-9]*'):
  try:
   if not (proc/'comm').read_text().strip().startswith('kwin_x11') and b'/armada-desktop.sh' not in (proc/'cmdline').read_bytes():continue
   for item in (proc/'environ').read_bytes().split(bytes([0])):
    if item.startswith(b'DBUS_SESSION_BUS_ADDRESS='):
     env['DBUS_SESSION_BUS_ADDRESS']=item.split(b'=',1)[1].decode()
  except OSError:continue
 if Path('/run/armada-session-bus').exists():env['DBUS_SESSION_BUS_ADDRESS']=Path('/run/armada-session-bus').read_text().strip()
 if 'DBUS_SESSION_BUS_ADDRESS' not in env:return b'No KWin session bus found'
 r=subprocess.run(['/usr/bin/chroot','/armada','/usr/bin/qdbus-qt6','org.kde.KWin','/KWin','supportInformation'],env=env,capture_output=True,text=True,timeout=10)
 return json.dumps({'returncode':r.returncode,'stdout':r.stdout[-32000:],'stderr':r.stderr[-4000:]}).encode()
def restartkwin(software=False,egl=False):
 bus=Path('/run/armada-session-bus').read_text().strip()
 env={**os.environ,'DBUS_SESSION_BUS_ADDRESS':bus,'DISPLAY':':0','XDG_RUNTIME_DIR':'/run/user/0','QT_QPA_PLATFORM':'xcb','QT_SCALE_FACTOR':'1.25','QT_FONT_DPI':'96','KWIN_COMPOSE':'N' if software else 'O2','KWIN_X11_REFRESH_RATE':'120000','KWIN_X11_FORCE_SOFTWARE_VSYNC':'1','KWIN_X11_NO_SYNC_TO_VBLANK':'1','KWIN_EXPLICIT_SYNC':'0'}
 if not software:env.update({'GALLIUM_DRIVER':'zink','MESA_LOADER_DRIVER_OVERRIDE':'zink','LIBGL_KOPPER_DRI2':'true','MESA_VK_WSI_DEBUG':'sw','VK_DRIVER_FILES':'/usr/share/vulkan/icd.d/freedreno_icd.aarch64.json'})
 else:env.update({'LIBGL_ALWAYS_SOFTWARE':'1','GALLIUM_DRIVER':'llvmpipe'})
 if not software:env.pop('LIBGL_ALWAYS_SOFTWARE',None)
 if egl:env['KWIN_OPENGL_INTERFACE']='egl'
 with open('/run/armada-kwin-restart.log','ab',buffering=0) as log:
  child=subprocess.Popen(['/usr/bin/chroot','/armada','/usr/bin/kwin_x11','--replace'],env=env,stdout=log,stderr=log,start_new_session=True)
 return json.dumps({'pid':child.pid,'software_compositor_fallback':software}).encode()
def wificonnect(payload):
 data=json.loads(base64.urlsafe_b64decode(payload))
 if set(data)!={'ssid','password'}:raise ValueError('Expected Wi-Fi SSID and password only')
 ssid,password=data['ssid'],data['password']
 if not isinstance(ssid,str) or not isinstance(password,str):raise ValueError('Invalid Wi-Fi values')
 if not 1<=len(ssid.encode())<=32 or not 8<=len(password.encode())<=63 or any(c in ssid+password for c in ['\0','\r','\n']):raise ValueError('Invalid SSID or WPA passphrase length')
 interfaces=[p.name for p in Path('/sys/class/net').glob('*') if (p/'wireless').is_dir()]
 if len(interfaces)!=1:raise ValueError('Expected exactly one wireless interface')
 interface=interfaces[0];identifier=str(uuid.uuid4())
 def escape(value):return value.replace('\\','\\\\').replace(' ','\\s')
 profile='[connection]\nid=OP13 RAM Wi-Fi\nuuid='+identifier+'\ntype=wifi\ninterface-name='+interface+'\nautoconnect=true\n[wifi]\nmode=infrastructure\nssid='+escape(ssid)+'\n[wifi-security]\nkey-mgmt=wpa-psk\npsk='+escape(password)+'\n[ipv4]\nmethod=auto\n[ipv6]\nmethod=auto\n'
 directory=Path('/armada/run/NetworkManager/system-connections');directory.mkdir(parents=True,exist_ok=True,mode=0o700)
 path=directory/'op13-ram.nmconnection'
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'w') as stream:os.fchmod(stream.fileno(),0o600);stream.write(profile)
 env={**os.environ,'DBUS_SYSTEM_BUS_ADDRESS':'unix:path=/run/dbus/system_bus_socket'}
 def nm(args,timeout=12):return subprocess.run(['/usr/bin/chroot','/armada','/usr/bin/nmcli']+args,env=env,capture_output=True,text=True,timeout=timeout)
 nm(['general','logging','level','INFO','domains','DEFAULT'])
 loaded=nm(['connection','load','/run/NetworkManager/system-connections/op13-ram.nmconnection'])
 if loaded.returncode:return json.dumps({'connected':False,'stage':'load','error':loaded.stderr}).encode()
 result=nm(['--wait','35','connection','up','uuid',identifier],45)
 state=nm(['-t','-f','GENERAL.STATE,GENERAL.CONNECTION,IP4.ADDRESS,IP4.GATEWAY','device','show',interface])
 out={'connected':result.returncode==0,'interface':interface,'result':result.stdout,'error':result.stderr,'state':state.stdout,'credentials_storage':'phone RAM only; not embedded in boot media'}
 if result.returncode==0:
  try:
   test=subprocess.run(['/usr/bin/chroot','/armada','/usr/bin/curl','--silent','--show-error','--interface',interface,'--connect-timeout','5','--max-time','12','-o','/dev/null','-w','%{http_code}','https://example.com'],capture_output=True,text=True,timeout=15)
   out['https_test']={'returncode':test.returncode,'http_status':test.stdout,'error':test.stderr}
  except Exception as e:out['https_test']={'error':str(e)}
 return json.dumps(out).encode()
def keyboardtest():
 env={**os.environ,'DISPLAY':':0','XDG_RUNTIME_DIR':'/run/user/0','QT_QPA_PLATFORM':'xcb','QT_IM_MODULE':'qtvirtualkeyboard','QT_SCALE_FACTOR':'1.25','QT_FONT_DPI':'96','GALLIUM_DRIVER':'zink','MESA_LOADER_DRIVER_OVERRIDE':'zink','LIBGL_KOPPER_DRI2':'true','MESA_VK_WSI_DEBUG':'sw','VK_DRIVER_FILES':'/usr/share/vulkan/icd.d/freedreno_icd.aarch64.json','QSG_RHI_BACKEND':'opengl'}
 env.pop('LIBGL_ALWAYS_SOFTWARE',None);env.pop('QT_QUICK_BACKEND',None);env.pop('QT_VIRTUALKEYBOARD_DESKTOP_DISABLE',None)
 env['DBUS_SESSION_BUS_ADDRESS']=Path('/run/armada-session-bus').read_text().strip()
 with open('/run/keyboard-test.log','ab',buffering=0) as log:
  child=subprocess.Popen(['/usr/bin/chroot','/armada','/usr/bin/kdialog','--title','On-screen keyboard test','--inputbox','Tap the text field below. No password is needed for this test.'],env=env,stdout=subprocess.DEVNULL,stderr=log,start_new_session=True)
 return json.dumps({'pid':child.pid,'qt_input_module':'qtvirtualkeyboard','scaling':1.25}).encode()
def write(fd,data):
 end=time.monotonic()+30
 while data:
  if time.monotonic()>end:raise TimeoutError('USB transmit timeout')
  if not select.select([], [fd], [], 1)[1]:continue
  try:n=os.write(fd,data[:65536]);data=data[n:]
  except BlockingIOError:continue
def reply(fd,kind,data,meta=None):
 write(fd,f'OP13RAM {kind} {len(data)} {json.dumps(meta or {},separators=(",",":"))}\n'.encode());write(fd,data);write(fd,b'\nOP13RAM END\n')
def command(fd,line):
 if line.startswith(b'WIFICONNECT '):reply(fd,'WIFICONNECT',wificonnect(line[len(b'WIFICONNECT '):].strip()));return
 cmd=line.strip().upper()
 if cmd==b'PING':reply(fd,'PONG',b'OP13RAMCONTROL')
 elif cmd==b'STATUS':reply(fd,'STATUS',status())
 elif cmd==b'LOGS':reply(fd,'LOGS',logs())
 elif cmd==b'KEYBOARDTEST':reply(fd,'KEYBOARDTEST',keyboardtest())
 elif cmd==b'KWINEGL':reply(fd,'KWINEGL',restartkwin(egl=True))
 elif cmd==b'KWINRESTART':reply(fd,'KWINRESTART',restartkwin())
 elif cmd==b'KWINFALLBACK':reply(fd,'KWINFALLBACK',restartkwin(True))
 elif cmd==b'RENDERTEST':reply(fd,'RENDERTEST',rendertest())
 elif cmd==b'DESKTOPSTATUS':reply(fd,'DESKTOPSTATUS',desktopstatus())
 elif cmd==b'RETRYGPU':reply(fd,'RETRYGPU',retrygpu())
 elif cmd==b'WIFICHECK':reply(fd,'WIFICHECK',wificheck())
 elif cmd==b'HARDWARE':reply(fd,'HARDWARE',hardware())
 elif cmd==b'GPUCHECK':reply(fd,'GPUCHECK',gpucheck())
 elif cmd==b'SCREENSHOT':
  data,meta=screenshot();reply(fd,'SCREENSHOT',data,meta)
 elif cmd==b'REBOOT':
  reply(fd,'REBOOT',b'Cold reboot requested');time.sleep(.3)
  libc=ctypes.CDLL(None,use_errno=True)
  if libc.reboot(0x01234567)!=0:raise OSError(ctypes.get_errno(),'reboot syscall failed')
 else:reply(fd,'ERROR',b'Allowed commands: PING STATUS LOGS HARDWARE GPUCHECK SCREENSHOT REBOOT')
if __name__=='__main__':
 print('USB CONTROL: waiting for host; fixed-command recovery service',flush=True)
 while True:
  fd=None
  try:
   fd=os.open('/dev/ttyGS0',os.O_RDWR|os.O_NOCTTY|os.O_NONBLOCK)
   a=termios.tcgetattr(fd);a[0]=0;a[1]=0;a[2]=termios.CLOCAL|termios.CREAD|termios.CS8;a[3]=0;a[4]=termios.B115200;a[5]=termios.B115200;a[6][termios.VMIN]=0;a[6][termios.VTIME]=0;termios.tcsetattr(fd,termios.TCSANOW,a);buf=b''
   while True:
    if not select.select([fd],[],[],1)[0]:continue
    try:data=os.read(fd,256)
    except BlockingIOError:continue
    if not data:time.sleep(.2);continue
    buf+=data
    if len(buf)>1024:buf=b'';continue
    while b'\n' in buf:
     line,buf=buf.split(b'\n',1)
     try:command(fd,line)
     except Exception as e:reply(fd,'ERROR',str(e).encode())
  except OSError as e:
   if e.errno not in [errno.EIO,errno.ENXIO,errno.ENOENT]:print('USB CONTROL:',e,flush=True)
  finally:
   if fd is not None:os.close(fd)
  time.sleep(1)
