#!/usr/bin/env python3
"""Add Armada's SM8750 render-only GPU wiring to the verified USB/touch FDT."""
from pathlib import Path
import json,re,subprocess,sys
p=Path(__file__).resolve().parent
root=p.parents[1]
sys.path.insert(0,str(root/'tools'))
from op13_fdt import read_fdt
base=root/'experimental/arch-usb-control-v1/OP13-USB.DTB'
patches=root/'experimental/armada-ram-v1/source/packages/kernel/patches'
headers=Path('/Volumes/DodgeGnomeBuild/usb-kernel-headers/usr/lib/modules/7.3.0-1-aarch64-ARCH/build/include')
subprocess.run(['dtc','-I','dtb','-O','dts','-o',str(p/'base.dts'),str(base)],check=True,stderr=subprocess.DEVNULL)
names=['0033-arm64-dts-qcom-sm8750-gpu-clock-controllers.patch','0038-arm64-dts-qcom-sm8750-add-GPU-nodes.patch']
added='\n'.join(line[1:] for name in names for line in (patches/name).read_text().splitlines() if line.startswith('+') and not line.startswith('+++') and not line.startswith('+#include'))
paths={
 'bi_tcxo_div2':'/clocks/bi-tcxo-div2-clk',
 'gcc':'/soc@0/clock-controller@100000',
 'rpmhpd':'/soc@0/rsc@16500000/power-controller',
 'rpmhpd_opp_low_svs':'/soc@0/rsc@16500000/power-controller/opp-table/opp-64',
 'gem_noc':'/soc@0/interconnect@24100000',
 'mc_virt':'/interconnect-1',
 'gpu_micro_code_mem':'/reserved-memory/gpu-micro-code@9b09a000',
 'aoss_qmp':'/soc@0/power-management@c300000',
}
before=read_fdt(base.read_bytes())
for label,path in paths.items():
 assert path in before,path
 added=re.sub(r'&'+label+r'\b','&{'+path+'}',added)
added=added.replace('0x03d00000 0x0 0x40000','0x03d00000 0x0 0x6c000')
includes=['clock/qcom,sm8750-gpucc.h','clock/qcom,kaanapali-gxclkctl.h','clock/qcom,sm8750-gcc.h','power/qcom,rpmhpd.h','power/qcom-rpmpd.h','interconnect/qcom,icc.h','interconnect/qcom,sm8750-rpmh.h','interrupt-controller/arm-gic.h']
text='\n'.join('#include <dt-bindings/'+n+'>' for n in includes)+'\n'+(p/'base.dts').read_text()+'\n/ { soc@0 {\n'+added+'\n}; };\n'
# Limit initial render validation to 222 MHz. Keep display ownership in EFI.
text+='&gpu { status = "okay"; };\n&gpu_zap_shader { firmware-name = "qcom/sm8750/oneplus/dodge/gen80000_zap.mbn"; };\n'
# Longer deferred probing otherwise brings the internal UFS controller up too.
# It is unnecessary for this RAM build; keep phone storage unavailable.
storage=['/soc@0/ufs@1d84000','/soc@0/phy@1d80000']
for path in storage:
 assert path in before
 text+='&{'+path+'} { status = "disabled"; };\n'
for hz in re.findall(r'opp-(\d+)\s*\{',added):
 if int(hz)>222000000 and int(hz)!=500000000 and int(hz)!=650000000 and int(hz)!=687500000:
  text+='&gpu_opp_table { /delete-node/ opp-'+hz+'; };\n'
(p/'gpu.dts').write_text(text)
r=subprocess.run(['/opt/homebrew/opt/llvm/bin/clang','-E','-P','-x','assembler-with-cpp','-nostdinc','-undef','-D__DTS__','-I'+str(headers),str(p/'gpu.dts')],capture_output=True,check=True)
(p/'gpu.preprocessed.dts').write_bytes(r.stdout)
r=subprocess.run(['dtc','-I','dts','-O','dtb','-o',str(p/'OP13-GPU.DTB'),str(p/'gpu.preprocessed.dts')],capture_output=True)
(p/'dtc-gpu.log').write_bytes(r.stderr);r.check_returncode()
after=read_fdt((p/'OP13-GPU.DTB').read_bytes())
assert after['/soc@0/display-subsystem@ae00000']['status']==b'disabled\0'
assert after['/soc@0/geniqup@ac0000/spi@a90000']['status']==b'disabled\0'
changes={}
for path,props in before.items():
 diff={key:(val.hex(),after[path].get(key,b'').hex()) for key,val in props.items() if after[path].get(key)!=val and not (path in storage and key=='status' and after[path][key]==b'disabled\0')}
 # Only dtc's regenerated phandles may augment existing providers.
 assert not diff,(path,diff)
 for key in after[path].keys()-props.keys():assert key=='phandle',(path,key)
new={path:{k:v.hex() for k,v in props.items()} for path,props in after.items() if path not in before}
(p/'gpu-fdt-changes.json').write_text(json.dumps({'added_nodes':new,'existing_node_properties_preserved_except_ufs_disabled':True,'storage_nodes_disabled':storage,'gpu_max_hz':222000000,'display_owned_by_efi':True},indent=2))
print('Verified GPU additions and UFS disabled; native MDSS stays disabled.')
