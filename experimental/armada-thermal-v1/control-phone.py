#!/usr/bin/env python3
"""Host client for the explicitly identified OP13 RAM USB recovery service."""
from pathlib import Path
import argparse,base64,getpass,glob,json,os,select,struct,termios,time,zlib,binascii
def png(data,meta):
 w,h,stride=meta['width'],meta['height'],meta['stride'];assert meta['format']=='BGRA8888' and len(data)==h*stride and w*4<=stride
 rows=[]
 for y in range(h):
  src=data[y*stride:y*stride+w*4];dst=bytearray(w*3);dst[0::3]=src[2::4];dst[1::3]=src[1::4];dst[2::3]=src[0::4];rows.append(b'\0'+dst)
 def chunk(t,d):return struct.pack('>I',len(d))+t+d+struct.pack('>I',binascii.crc32(t+d)&0xffffffff)
 return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>2I5B',w,h,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(rows)))+chunk(b'IEND',b'')
def transact(fd,command,timeout=45):
 os.write(fd,command.encode()+b'\n');buf=bytearray();deadline=time.monotonic()+timeout
 def extend():
  if time.monotonic()>deadline:raise TimeoutError('No complete USB recovery response')
  if select.select([fd],[],[],min(1,max(0,deadline-time.monotonic())))[0]:
   b=os.read(fd,65536)
   if b:buf.extend(b)
 while b'\n' not in buf:extend()
 line,_,rest=buf.partition(b'\n');buf=bytearray(rest)
 prefix,kind,length,metadata=line.decode().split(' ',3);assert prefix=='OP13RAM'
 n=int(length);assert 0<=n<=32*1024*1024
 while len(buf)<n+len(b'\nOP13RAM END\n'):extend()
 assert buf[n:]==b'\nOP13RAM END\n'
 return kind,bytes(buf[:n]),json.loads(metadata)
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('command',choices=['thermalstatus','thermaltest','ping','steamscreenshot','cpustatus','clocksync','steamstatus','steamrestart','steamsoftware','steamstart','fastfetch','btstatus','status','logs','screenshot','reboot','hardware','gpucheck','retrygpu','wificheck','rendertest','desktopstatus','kwinrestart','kwinfallback','kwinegl','wificonnect','keyboardtest']);ap.add_argument('--port');ap.add_argument('--output',type=Path);ap.add_argument('--ssid');args=ap.parse_args()
 if args.command=='screenshot' and not args.output:ap.error('screenshot requires --output')
 ports=[args.port] if args.port else glob.glob('/dev/cu.usbmodemOP13RAMCONTROL*')
 if len(ports)!=1:raise SystemExit('Expected one identified OP13 RAM USB port; inspect USB enumeration and supply --port explicitly')
 fd=os.open(ports[0],os.O_RDWR|os.O_NOCTTY|os.O_NONBLOCK)
 try:
  a=termios.tcgetattr(fd);a[0]=0;a[1]=0;a[2]=termios.CLOCAL|termios.CREAD|termios.CS8;a[3]=0;a[4]=termios.B115200;a[5]=termios.B115200;a[6][termios.VMIN]=0;a[6][termios.VTIME]=0;termios.tcsetattr(fd,termios.TCSANOW,a);termios.tcflush(fd,termios.TCIOFLUSH)
  kind,data,meta=transact(fd,'PING',10);assert kind=='PONG' and data==b'OP13RAMCONTROL'
  command=args.command.upper()
  if args.command=='clocksync':command+=' '+str(int(time.time()))
  if args.command=='wificonnect':
   if not args.ssid:ap.error('wificonnect requires --ssid')
   password=getpass.getpass('Wi-Fi password (not stored on Mac or in boot media): ')
   command+=' '+base64.urlsafe_b64encode(json.dumps({'ssid':args.ssid,'password':password}).encode()).decode()
  kind,data,meta=transact(fd,command,90 if args.command in ['gpucheck','wificonnect'] else 45)
  if kind=='ERROR':raise RuntimeError(data.decode())
  if args.output:args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_bytes(png(data,meta) if kind=='SCREENSHOT' else data);print(str(args.output))
  else:print(data.decode())
 finally:os.close(fd)
if __name__=='__main__':main()
