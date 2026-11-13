from pathlib import Path
import sys,subprocess,json
p=Path(__file__).resolve().parent;root=p.parents[1];sys.path.insert(0,str(root/'tools'))
from op13_fdt import read_fdt
base=p.parent/'armada-native-v1/OP13-NATIVE.DTB';before=read_fdt(base.read_bytes())
subprocess.run(['dtc','-I','dtb','-O','dts','-o',str(p/'base.dts'),str(base)],check=True,stderr=subprocess.DEVNULL)
mdss='/soc@0/display-subsystem@ae00000';dsi=mdss+'/dsi@ae94000';panel=dsi+'/panel@0';phy=mdss+'/phy@ae95000'
def regulator(name):
 found=[path for path,props in before.items() if props.get('regulator-name')==name.encode()+b'\0'];assert len(found)==1,(name,found);return found[0]
changes={mdss:{'status':'"okay"'},dsi:{'vdda-supply':'<&{'+regulator('vreg_l3g_1p2')+'}>'},phy:{'vdds-supply':'<&{'+regulator('vreg_l3i_0p88')+'}>'},panel:{'vddio-supply':'<&{'+regulator('vreg_l12b_1p8')+'}>','vci-supply':'<&{'+regulator('vreg_l13b_3p0')+'}>'}}
# Match the OnePlus 13 panel VCI rail to the stock 3.0V configuration.
changes[regulator('vreg_l13b_3p0')]={'regulator-min-microvolt':'<3000000>','regulator-max-microvolt':'<3000000>'}
text=(p/'base.dts').read_text()
for node,props in changes.items():
 assert node in before,node
 text+='\n&{'+node+'} { '+ ' '.join(k+' = '+v+';' for k,v in props.items())+' };\n'
(p/'wayland.dts').write_text(text)
r=subprocess.run(['dtc','-I','dts','-O','dtb','-o',str(p/'OP13-WAYLAND.DTB'),str(p/'wayland.dts')],capture_output=True);(p/'dtc.log').write_bytes(r.stderr);r.check_returncode()
after=read_fdt((p/'OP13-WAYLAND.DTB').read_bytes())
assert before.keys()==after.keys()
for node,props in before.items():
 for k,v in props.items():
  if k not in changes.get(node,{}):assert after[node][k]==v,(node,k)
for node in ['/soc@0/ufs@1d84000','/soc@0/phy@1d80000','/soc@0/geniqup@ac0000/spi@a90000']:assert after[node]['status']==b'disabled\0'
(p/'fdt-changes.json').write_text(json.dumps(changes,indent=2));print('Only display properties changed; UFS and touch SPI disabled.')
