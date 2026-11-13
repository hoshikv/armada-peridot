#!/usr/bin/python
"""Register actual kernel input devices explicitly with framebuffer Xorg."""
import fcntl,json,os,struct
from pathlib import Path
def query(fd,nr,size):
    data=bytearray(size)
    fcntl.ioctl(fd,0x80000000|(size<<16)|(ord('E')<<8)|nr,data,True)
    return data
def bit(data,n):return bool(data[n//8]&(1<<(n%8)))
records=[];devices=[]
for event in sorted(Path('/dev/input').glob('event*')):
    record={'path':str(event)}
    try:
        with event.open('rb',buffering=0) as f:
            name=bytes(query(f.fileno(),6,256)).split(b'\0')[0].decode(errors='replace')
            ev=query(f.fileno(),0x20,32)
            absolute=query(f.fileno(),0x23,64) if bit(ev,3) else bytes(64)
            keys=query(f.fileno(),0x21,128) if bit(ev,1) else bytes(128)
            is_touch=bit(ev,3) and ((bit(absolute,53) and bit(absolute,54)) or (bit(absolute,0) and bit(absolute,1) and bit(keys,330)))
            record.update(name=name,touch_candidate=is_touch)
            if is_touch:devices.append(str(event))
    except OSError as e:record['error']=str(e)
    records.append(record)
Path('/run/touch-input.json').write_text(json.dumps(records,indent=2)+'\n')
print(json.dumps(records,indent=2),flush=True)
p=Path('/etc/X11/dodge-fbdev.conf');config=p.read_text()
inputs=''
for i,device in enumerate(devices):
    ident=f'PhoneTouch{i}'
    inputs+=f'\nSection "InputDevice"\n Identifier "{ident}"\n Driver "evdev"\n Option "Device" "{device}"\n Option "IgnoreRelativeAxes" "true"\nEndSection\n'
    config=config.replace(' Identifier "Dodge"\n',f' Identifier "Dodge"\n InputDevice "{ident}" "SendCoreEvents"\n',1)
p.write_text(config+inputs)
print('Explicit Xorg touchscreen devices:',len(devices),flush=True)
