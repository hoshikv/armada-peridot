#!/usr/bin/env python3
"""Bounded USB2 peripheral configuration in a copy of the working RAM FDT."""
from pathlib import Path
import json,struct,sys
p=Path(__file__).resolve().parent;project=p.parents[1]
sys.path.insert(0,str(project/'tools'))
from op13_fdt import read_fdt
data=(project/'experimental/arch-gnome-touch-v1/OP13.DTB').read_bytes();before=read_fdt(data)
usb='/soc@0/usb@a6f8800/usb@a600000';phy='/soc@0/phy@88e8000'
assert before[usb]['compatible']==b'snps,dwc3\0'
assert before['/soc@0/phy@88e3000']['compatible']==b'qcom,sm8750-m31-eusb2-phy\0'
changes={usb:{'dr_mode':b'peripheral\0','maximum-speed':b'high-speed\0','phys':before[usb]['phys'][:4],'phy-names':b'usb2-phy\0','usb-role-switch':None},phy:{'status':b'disabled\0'}}
# EFI owns scanout in this build. Do not attach the native MDSS device to a
# fresh, empty DMA domain when the newly available interconnect starts SMMU.
# Unclaimed firmware streams retain the Qcom driver's boot-time bypass handling.
display='/soc@0/display-subsystem@ae00000'
assert before[display]['compatible']==b'qcom,sm8750-mdss\0'
changes[display]={'status':b'disabled\0'}
# No Type-C role controller is needed for this fixed, USB2-only device link.
# Remove USB graph links that would otherwise defer probing on that controller.
endpoints=set()
for path,props in before.items():
 if path.startswith(usb+'/ports/') and 'phandle' in props:endpoints.add(props['phandle'])
for path,props in before.items():
 if path.startswith(usb+'/ports/') or props.get('remote-endpoint') in endpoints:
  if 'remote-endpoint' in props:changes.setdefault(path,{})['remote-endpoint']=None
h=list(struct.unpack_from('>10I',data));start,strings,size,names_size=h[2],h[3],h[9],h[8]
assert strings>=start+size
names=bytearray(data[strings:strings+names_size]);offsets={};o=0
for name in names.split(b'\0'):offsets[name.decode()]=o;o+=len(name)+1
for props in changes.values():
 for name in props:
  if name not in offsets:offsets[name]=len(names);names.extend(name.encode()+b'\0')
out=bytearray();stack=[];pos=start
def prop(name,value):
 out.extend(struct.pack('>III',3,len(value),offsets[name])+value+b'\0'*(-len(value)%4))
while pos<start+size:
 begin=pos;tag=struct.unpack_from('>I',data,pos)[0];pos+=4
 if tag==1:
  end=data.index(0,pos,start+size);stack.append(data[pos:end].decode());pos=(end+4)&~3;out.extend(data[begin:pos])
  for name,value in changes.get('/'.join(stack),{}).items():
   if value is not None:prop(name,value)
 elif tag==2:stack.pop();out.extend(data[begin:pos])
 elif tag==3:
  n,nameoff=struct.unpack_from('>II',data,pos);pos+=8;name=bytes(names[nameoff:names.index(0,nameoff)]).decode();pos=(pos+n+3)&~3
  if name not in changes.get('/'.join(stack),{}):out.extend(data[begin:pos])
 elif tag==4:out.extend(data[begin:pos])
 elif tag==9:out.extend(data[begin:start+size]);break
 else:raise ValueError(tag)
gap=data[start+size:strings];result=bytearray(data[:start]+out+gap+names)
h[1]=len(result);h[3]=start+len(out)+len(gap);h[8]=len(names);h[9]=len(out);struct.pack_into('>10I',result,0,*h)
expected={path:dict(props) for path,props in before.items()}
for path,props in changes.items():
 for name,value in props.items():
  if value is None:expected[path].pop(name,None)
  else:expected[path][name]=value
assert read_fdt(result)==expected,'Unexpected device-tree change'
assert expected['/soc@0/geniqup@ac0000/spi@a90000']['status']==b'disabled\0'
(p/'OP13-USB.DTB').write_bytes(result)
(p/'fdt-changes.json').write_text(json.dumps({path:{k:v.hex() if v is not None else None for k,v in props.items()} for path,props in changes.items()},indent=2))
print('Verified only listed USB2 properties and native MDSS status changed; touch SPI stays disabled.')
