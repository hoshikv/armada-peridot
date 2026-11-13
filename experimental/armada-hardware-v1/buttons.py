#!/usr/bin/python
"""RAM-only power display toggle; logs only power/volume keys, never text."""
from pathlib import Path
import os,select,struct,fcntl,subprocess,time
fmt=struct.Struct('llHHi');devices={};off=False
print('Button bridge starting',flush=True)
def command(args):
 env={**os.environ,'XDG_RUNTIME_DIR':'/run/user/0','WAYLAND_DISPLAY':'wayland-0','QT_QPA_PLATFORM':'wayland'}
 bus=Path('/run/armada-session-bus')
 if not bus.exists():return
 env['DBUS_SESSION_BUS_ADDRESS']=bus.read_text().strip()
 r=subprocess.run(['/usr/bin/chroot','/armada']+args,env=env,capture_output=True,text=True,timeout=8)
 print('action',args,'exit',r.returncode,r.stderr[-500:],flush=True)
while True:
 for node in Path('/dev/input').glob('event*'):
  if str(node) in [p for fd,p in devices.items()]:continue
  try:
   fd=os.open(node,os.O_RDONLY|os.O_NONBLOCK);bits=bytearray(128);fcntl.ioctl(fd,0x80804521,bits,True)
   if not any(bits[k//8] & (1<<(k%8)) for k in [114,115,116]):os.close(fd);continue
   if bits[116//8] & (1<<(116%8)):fcntl.ioctl(fd,0x40044590,struct.pack('i',1))
   devices[fd]=str(node);print('BUTTON DEVICE',node,flush=True)
  except OSError:continue
 if not devices:time.sleep(1);continue
 ready,_,_=select.select(list(devices),[],[],1)
 for fd in ready:
  try:data=os.read(fd,fmt.size*64)
  except OSError:continue
  for at in range(0,len(data)-fmt.size+1,fmt.size):
   _,_,typ,code,value=fmt.unpack_from(data,at)
   if typ!=1 or code not in [114,115,116]:continue
   print('KEY',code,'VALUE',value,flush=True)
   if code==116 and value==1:
    off=not off;command(['/usr/bin/kscreen-doctor','--dpms','off' if off else 'on'])
