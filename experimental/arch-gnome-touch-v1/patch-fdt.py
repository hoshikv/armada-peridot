#!/usr/bin/env python3
"""Disable only the touch SPI controller in a host copy of the firmware FDT."""
from pathlib import Path
import argparse,struct,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
from op13_fdt import read_fdt
TARGET='/soc@0/geniqup@ac0000/spi@a90000'
def patch(data):
    before=read_fdt(data)
    if TARGET not in before:raise ValueError('Expected OP13 touch SPI controller absent')
    h=list(struct.unpack_from('>10I',data))
    _,total,start,strings,_,_,_,_,names_size,size=h
    if strings<start+size:raise ValueError('Unsupported FDT block order')
    names=data[strings:strings+names_size]
    offset=0;status=None
    for name in names.split(b'\0'):
        if name==b'status':status=offset;break
        offset+=len(name)+1
    if status is None:raise ValueError('FDT status property name absent')
    out=bytearray();pos=start;stack=[]
    while pos<start+size:
        began=pos;tag=struct.unpack_from('>I',data,pos)[0];pos+=4
        if tag==1:
            end=data.index(0,pos,start+size);stack.append(data[pos:end].decode());pos=(end+4)&~3
            out+=data[began:pos]
            if '/'.join(stack)==TARGET:
                value=b'disabled\0';out+=struct.pack('>III',3,len(value),status)+value+b'\0'*(-len(value)%4)
        elif tag==2:
            stack.pop();out+=data[began:pos]
        elif tag==3:
            n,name=struct.unpack_from('>II',data,pos);pos+=8
            property_name=names[name:names.index(0,name)]
            pos=(pos+n+3)&~3
            if '/'.join(stack)!=TARGET or property_name!=b'status':out+=data[began:pos]
        elif tag==4:out+=data[began:pos]
        elif tag==9:
            out+=data[began:start+size];break
        else:raise ValueError('Unexpected FDT token')
    gap=data[start+size:strings]
    result=bytearray(data[:start]+out+gap+data[strings:total])
    h[1]=len(result);h[3]=start+len(out)+len(gap);h[9]=len(out)
    struct.pack_into('>10I',result,0,*h)
    after=read_fdt(result)
    expected={path:dict(props) for path,props in before.items()}
    expected[TARGET]['status']=b'disabled\0'
    if after!=expected:raise ValueError('Unexpected device-tree mutation')
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    a.output.write_bytes(patch(a.source.read_bytes()))
    print('Verified: only touch SPI controller status changed to disabled')
