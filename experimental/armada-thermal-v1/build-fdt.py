from pathlib import Path
import re,sys,subprocess,json
p=Path(__file__).resolve().parent;root=p.parents[1];sys.path.insert(0,str(root/'tools'))
from op13_fdt import read_fdt,cells
base=p.parent/'armada-hardware-v1/OP13-HARDWARE.DTB';before=read_fdt(base.read_bytes());source=(p/'sm8750-thermal.dtsi').read_text()
def getblock(text,start):
 at=text.index(start);end=text.index('{',at)+1;depth=1
 while depth:
  depth+=(text[end]=='{')-(text[end]=='}');end+=1
 return text[at:end+1]
thermal=getblock(source,'thermal-zones {')
for name in re.findall(r'\n\s*(cpu-[^\s]+-thermal) \{',thermal):
 old=getblock(thermal,name+' {');new=old.replace('temperature = <90000>','temperature = <70000>').replace('temperature = <95000>','temperature = <80000>').replace('temperature = <120000>','temperature = <90000>').replace('temperature = <125000>','temperature = <95000>').replace('hysteresis = <2000>','hysteresis = <3000>')
 new=new.replace(name+' {',name+' {\n\t\t\tpolling-delay = <1000>;',1);thermal=thermal.replace(old,new)
cpus=['/cpus/cpu@'+n for n in ['0','100','200','300','400','500','10000','10100']]
for i,path in enumerate(cpus):thermal=re.sub(r'&cpu'+str(i)+r'\b','&{'+path+'}',thermal)
subprocess.run(['dtc','-I','dtb','-O','dts','-o',str(p/'base.dts'),str(base)],check=True,stderr=subprocess.DEVNULL)
text='\n'.join('#include <dt-bindings/'+s+'>' for s in ['interrupt-controller/arm-gic.h','thermal/thermal.h'])+'\n'+(p/'base.dts').read_text()
text+='\n/ { firmware {\n'+getblock(source,'scmi {')+'\n}; soc@0 {\n'
for label,node in [('tsens0','thermal-sensor@c228000'),('tsens1','thermal-sensor@c229000'),('tsens2','thermal-sensor@c22a000'),('tsens3','thermal-sensor@c22b000'),('cpucp_mbox','mailbox@16430000'),('sram','sram@17b4e000')]:
 assert '/soc@0/'+node not in before
 text+=getblock(source,label+': '+node+' {')+'\n'
text+='};\n'+thermal+'\n};\n'
for i,path in enumerate(cpus):
 old=cells(before[path]['power-domains']);assert len(old)==1
 text+='&{'+path+'} { power-domains = <'+str(old[0])+'>, <&scmi_dvfs '+str(0 if i<6 else 1)+'>; power-domain-names = "psci", "perf"; #cooling-cells = <2>; };\n'
(p/'thermal.dts').write_text(text)
headers='/Volumes/DodgeGnomeBuild/usb-kernel-headers/usr/lib/modules/7.3.0-1-aarch64-ARCH/build/include'
r=subprocess.run(['/opt/homebrew/opt/llvm/bin/clang','-E','-P','-x','assembler-with-cpp','-nostdinc','-undef','-D__DTS__','-I'+headers,str(p/'thermal.dts')],capture_output=True,check=True);(p/'thermal.preprocessed.dts').write_bytes(r.stdout)
r=subprocess.run(['dtc','-I','dts','-O','dtb','-o',str(p/'OP13-THERMAL.DTB'),str(p/'thermal.preprocessed.dts')],capture_output=True);(p/'dtc.log').write_bytes(r.stderr);r.check_returncode();after=read_fdt((p/'OP13-THERMAL.DTB').read_bytes())
for path,props in before.items():
 for key,value in props.items():
  if path in cpus and key in ['power-domains','power-domain-names']:continue
  assert after[path][key]==value,(path,key)
for path in ['/soc@0/ufs@1d84000','/soc@0/phy@1d80000','/soc@0/geniqup@ac0000/spi@a90000']:assert after[path]['status']==b'disabled\0'
assert len([n for n in after if n.startswith('/thermal-zones/cpu-') and n.count('/')==2])==16
(p/'fdt-changes.json').write_text(json.dumps({'added_nodes':list(after.keys()-before.keys()),'cpu_performance_domains_added':cpus,'cpu_passive_trips_millicelsius':[70000,80000],'cpu_hot_millicelsius':90000,'cpu_critical_millicelsius':95000,'source':'Exact Linux7.3 SM8750 DTSI plus Armada0037 CPUcooling maps; lower trips selected for experimental phone port','other_existing_properties_unchanged':True,'phone_storage_writes':False},indent=2)+'\n')
print('SCMI DVFS, CPUcooling maps and four TSENS blocks added; existing peripheral/storage settings preserved.')
