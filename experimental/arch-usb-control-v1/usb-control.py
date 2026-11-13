#!/usr/bin/python
"""Local USB CDC recovery protocol. Fixed read-only commands plus cold reboot."""
from pathlib import Path
import ctypes,errno,json,os,select,subprocess,termios,time
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
 for name in ['usb-startup','touch-bridge','armada-session','armada-kwin','armada-plasma','armada-konsole']:
  f=Path('/run/'+name+'.log')
  if f.exists():out.extend(('\n--- '+name+' ---\n').encode()+f.read_bytes()[-24000:])
 out.extend(b'\n--- dmesg ---\n'+subprocess.run(['/usr/bin/dmesg'],capture_output=True,timeout=5).stdout[-120000:])
 return bytes(out)
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
 cmd=line.strip().upper()
 if cmd==b'PING':reply(fd,'PONG',b'OP13RAMCONTROL')
 elif cmd==b'STATUS':reply(fd,'STATUS',status())
 elif cmd==b'LOGS':reply(fd,'LOGS',logs())
 elif cmd==b'SCREENSHOT':
  data,meta=screenshot();reply(fd,'SCREENSHOT',data,meta)
 elif cmd==b'REBOOT':
  reply(fd,'REBOOT',b'Cold reboot requested');time.sleep(.3)
  libc=ctypes.CDLL(None,use_errno=True)
  if libc.reboot(0x01234567)!=0:raise OSError(ctypes.get_errno(),'reboot syscall failed')
 else:reply(fd,'ERROR',b'Allowed commands: PING STATUS LOGS SCREENSHOT REBOOT')
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
