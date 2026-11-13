from pathlib import Path
import subprocess,sys,json
p=Path(__file__).resolve().parent;sys.path.insert(0,str(p.parents[1]/'tools'))
from op13_fdt import read_fdt
base=p.parent/'armada-wayland-v1/OP13-WAYLAND.DTB';before=read_fdt(base.read_bytes())
subprocess.run(['dtc','-I','dtb','-O','dts','-o',str(p/'base.dts'),str(base)],check=True,stderr=subprocess.DEVNULL)
uart='/soc@0/geniqup@8c0000/serial@898000';pmu='/wcn7860-pmu';gpio='/soc@0/spmi@c400000/pmic@5/gpio@8800'
text=(p/'base.dts').read_text()+'''
&{/soc@0/geniqup@8c0000} { status = "okay"; };

&{/soc@0/pinctrl@f100000} {
 bt_default: bt-default-state { sw-ctrl-pins { pins = "gpio18"; function = "gpio"; bias-pull-down; }; };
};
&{/wcn7860-pmu} {
 bt-enable-gpios = <&{/soc@0/spmi@c400000/pmic@5/gpio@8800} 3 0>;
 pinctrl-names = "default";
 pinctrl-0 = <&bt_default>;
};
&{/soc@0/geniqup@8c0000/serial@898000} {
 status = "okay";
 bluetooth {
  compatible = "qcom,wcn7860-bt";
  vddrfacmn-supply = <&{/wcn7860-pmu/regulators/ldo0}>;
  vddaon-supply = <&{/wcn7860-pmu/regulators/ldo1}>;
  vddwlcx-supply = <&{/wcn7860-pmu/regulators/ldo2}>;
  vddwlmx-supply = <&{/wcn7860-pmu/regulators/ldo3}>;
  vddrfa0p8-supply = <&{/wcn7860-pmu/regulators/ldo5}>;
  vddrfa1p2-supply = <&{/wcn7860-pmu/regulators/ldo6}>;
  vddrfa1p8-supply = <&{/wcn7860-pmu/regulators/ldo7}>;
  max-speed = <3200000>;
 };
};
'''
(p/'hardware.dts').write_text(text)
r=subprocess.run(['dtc','-I','dts','-O','dtb','-o',str(p/'OP13-HARDWARE.DTB'),str(p/'hardware.dts')],capture_output=True);(p/'dtc.log').write_bytes(r.stderr);r.check_returncode()
after=read_fdt((p/'OP13-HARDWARE.DTB').read_bytes());allowed={'/soc@0/geniqup@8c0000':{'status'},uart:{'status'},pmu:{'bt-enable-gpios','pinctrl-names','pinctrl-0'}}
for node,props in before.items():
 for key,val in props.items():
  if key not in allowed.get(node,set()):assert after[node][key]==val,(node,key)
for node in ['/soc@0/ufs@1d84000','/soc@0/phy@1d80000','/soc@0/geniqup@ac0000/spi@a90000']:assert after[node]['status']==b'disabled\0'
(p/'fdt-changes.json').write_text(json.dumps({'changed_existing':{k:list(v) for k,v in allowed.items()},'new_nodes':list(after.keys()-before.keys()),'audio_changes':False},indent=2));print('Bluetooth-only DT changes; audio/display/storage unchanged.')
