#!/usr/bin/python
"""Fixed 75C synthetic sensor test. Does not heat/stress the phone."""
from pathlib import Path
import importlib.util,json,time
s=importlib.util.spec_from_file_location('g','/thermal-guard.py');g=importlib.util.module_from_spec(s);s.loader.exec_module(g)
state=json.loads(Path('/run/thermal-state.json').read_text())
assert state['phase']=='ready' and time.monotonic()-state['monotonic']<3
assert state['peak_cpu_millicelsius']<65000,'Wait for a cool device'
zone=next(z for z in Path('/sys/class/thermal').glob('thermal_zone*') if (z/'type').read_text().strip()=='cpu-0-0-0-thermal')
result={'input':'synthetic 75000 mC; no physical heating','before':state,'samples':[]}
try:
 (zone/'emul_temp').write_text('75000')
 for i in range(6):
  time.sleep(1);result['samples'].append(json.loads(Path('/run/thermal-state.json').read_text()))
finally:(zone/'emul_temp').write_text('0')
time.sleep(2)
result['after']=json.loads(Path('/run/thermal-state.json').read_text())
result['guard_throttled']=any(s['level']=='warm' and all(int(p['scaling_max_freq'])<=max(1000000,int(p['cpuinfo_min_freq'])) for p in s['policies'].values()) for s in result['samples'])
result['kernel_cooling_acted']=any(any(c['cur_state']>0 for c in s['cooling']) for s in result['samples'])
print(json.dumps(result))
