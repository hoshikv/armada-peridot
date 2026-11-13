#!/usr/bin/env python3
"""Add native PCIe0/WCN7860 using stock OnePlus rails and GPIOs, RAM only."""
from pathlib import Path
import json,re,subprocess,sys
p=Path(__file__).resolve().parent;root=p.parents[1]
sys.path.insert(0,str(root/'tools'))
from op13_fdt import read_fdt,cells
base=read_fdt((p/'OP13-GPU.DTB').read_bytes())
stock=read_fdt((root/'source/vendor-mu-silicium/Resources/DTBs/dodge.dtb').read_bytes())
cnss=stock['/soc/qcom,cnss-peach@b0000000']
assert cells(cnss['wlan-en-gpio'])[1]==16
assert cells(stock['/soc/pcie@1c00000']['perst-gpio'])[1]==102
assert cells(stock['/soc/pcie@1c00000']['wake-gpio'])[1]==104
text=(p/'gpu.dts').read_text()
text='\n'.join('#include <dt-bindings/'+s+'>' for s in ['clock/qcom,rpmh.h','clock/qcom,sm8750-tcsr.h','gpio/gpio.h'])+'\n'+text
nodes=(p/'pcie0.dtsi').read_text()+'\n'+(p/'pcie0_phy.dtsi').read_text()
externals={
 'gcc':'/soc@0/clock-controller@100000','tcsrcc':'/soc@0/clock-controller@f204008',
 'apps_smmu':'/soc@0/iommu@15000000','cnoc_main':'/soc@0/interconnect@1500000',
 'gem_noc':'/soc@0/interconnect@24100000','mc_virt':'/interconnect-1',
 'gic_its':'/soc@0/interrupt-controller@16000000/msi-controller@16040000',
 'intc':'/soc@0/interrupt-controller@16000000','pcie_noc':'/soc@0/interconnect@16c0000',
 'rpmhpd_opp_low_svs':'/soc@0/rsc@16500000/power-controller/opp-table/opp-64',
 'rpmhpd_opp_nom':'/soc@0/rsc@16500000/power-controller/opp-table/opp-256',
 'tlmm':'/soc@0/pinctrl@f100000','rpmhcc':'/soc@0/rsc@16500000/clock-controller',
}
for k,v in externals.items():assert v in base,(k,v)
donor=(root/'experimental/armada-ram-v1/source/packages/kernel/dts/sm8750-konkr-pf-elite.dts').read_text()
def block(start):
 at=donor.index(start);end=donor.index('{',at)+1;depth=1
 while depth:
  depth+=(donor[end]=='{')-(donor[end]=='}');end+=1
 return donor[at:end+1]
pmu=block('wcn7860-pmu {')
pmu=re.sub(r'\s*bt-enable-gpios = [^;]+;','',pmu)
supplies={'vreg_l3f_1p8':'regulators-2/ldo3','vreg_l2f_1p2':'regulators-2/ldo2','vreg_s4d_0p85':'regulators-1/smps4','vreg_s5f_0p85':'regulators-2/smps5','vreg_s7i_1p2':'regulators-4/smps7','vreg_s3g_1p8':'regulators-3/smps3'}
for k,v in supplies.items():externals[k]='/soc@0/rsc@16500000/'+v
extra='''
&pcie0 { pinctrl-0 = <&pcie0_default_state>; pinctrl-names = "default"; status = "okay"; max-link-speed = <3>; num-lanes = <2>; };
&pcie0_phy { status = "okay"; vdda-phy-supply = <&{/soc@0/rsc@16500000/regulators-2/ldo1}>; vdda-pll-supply = <&{/soc@0/rsc@16500000/regulators-3/ldo3}>; };
'''+block('&pcieport0 {')
text+='\n/ { soc@0 {\n'+nodes+'\n};\n'+pmu+'\n};\n'
text+='&{/soc@0/pinctrl@f100000} {\n'+(p/'pcie0_default_state.dtsi').read_text()+'\n};\n'+extra
for k,v in externals.items():text=re.sub(r'&'+k+r'\b','&{'+v+'}',text)
# Stock CNSS rail requests, within the stock provider's allowed range.
requests=[('vdd-wlan-aon','regulators-1/smps4'),('vdd-wlan-dig','regulators-2/smps5'),('vdd-wlan-rfa2','regulators-4/smps7')]
changed={}
for name,node in requests:
 path='/soc@0/rsc@16500000/'+node;lo,hi=cells(cnss['qcom,'+name+'-config'])[:2]
 assert cells(base[path]['regulator-min-microvolt'])[0]<=lo<=cells(base[path]['regulator-max-microvolt'])[0]
 text+='&{'+path+'} { regulator-min-microvolt = <'+str(lo)+'>; };\n';changed[path]=lo
# Linux 7.3's PCI controller still assumes the legacy four-cell map; its OF
# layer explicitly accepts that form for two-cell ARM SMMU providers.
source=(p/'pcie-qcom.c').read_text()
if 'u32 smmu_sid_len;' in source:
 assert 'of_check_bad_map' in (p/'base.c').read_text()
 text+='&pcie0 { iommu-map = <0 &{/soc@0/iommu@15000000} 0x1400 1>, <0x100 &{/soc@0/iommu@15000000} 0x1401 1>; };\n'
(p/'wifi.dts').write_text(text)
headers='/Volumes/DodgeGnomeBuild/usb-kernel-headers/usr/lib/modules/7.3.0-1-aarch64-ARCH/build/include'
r=subprocess.run(['/opt/homebrew/opt/llvm/bin/clang','-E','-P','-x','assembler-with-cpp','-nostdinc','-undef','-D__DTS__','-I'+headers,str(p/'wifi.dts')],capture_output=True,check=True)
(p/'wifi.preprocessed.dts').write_bytes(r.stdout)
r=subprocess.run(['dtc','-I','dts','-O','dtb','-o',str(p/'OP13-NATIVE.DTB'),str(p/'wifi.preprocessed.dts')],capture_output=True)
(p/'dtc-wifi.log').write_bytes(r.stderr);r.check_returncode()
after=read_fdt((p/'OP13-NATIVE.DTB').read_bytes())
for path,props in base.items():
 for key,val in props.items():
  if path in changed and key=='regulator-min-microvolt':assert cells(after[path][key])==[changed[path]]
  else:assert after[path][key]==val,(path,key)
assert after['/soc@0/display-subsystem@ae00000']['status']==b'disabled\0'
assert after['/soc@0/geniqup@ac0000/spi@a90000']['status']==b'disabled\0'
(p/'wifi-fdt-changes.json').write_text(json.dumps({'added_nodes':[k for k in after if k not in base],'stock_cnss_minimum_uv':changed,'bluetooth_enabled':False,'pcie_test_gen':3,'pcie_test_lanes':2,'native_display_enabled':False},indent=2))
print('Native Wi-Fi FDT verified against stock OnePlus GPIO/rail data; MDSS and touch SPI stay disabled.')
