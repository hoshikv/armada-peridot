#!/usr/bin/python
"""RAM-only thermal supervision. Sysfs frequency units are kHz; temperatures mC."""
from pathlib import Path
import ctypes,json,os,re,subprocess,time
RUN=Path('/run'); SYS=Path('/sys')
GPU_EXPECTED={f'gpuss{i}-thermal' for i in range(8)}
EXPECTED={f'cpu-{cluster}-{core}-{sensor}-thermal' for cluster,count in [(0,6),(1,2)] for core in range(count) for sensor in range(2)}

def next_level(temp,previous):
    if not 0 <= temp <= 130000:raise ValueError('Invalid CPU temperature')
    if temp>=85000:return 'reboot'
    if temp>=80000 or previous=='minimum' and temp>=75000:return 'minimum'
    if temp>=70000 or previous in ['warm','minimum'] and temp>=65000:return 'warm'
    return 'normal'

def choose_cap(available,target):
    choices=sorted(set(available))
    valid=[n for n in choices if 0<n<=target]
    if not valid:raise ValueError(f'No firmware CPU frequency at or below {target} kHz')
    return max(valid)

def atomic_json(path,value):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value));temp.replace(path)

def reboot(reason):
    (RUN/'thermal-ready').unlink(missing_ok=True)
    print('THERMAL RECOVERY: '+reason,flush=True)
    atomic_json(RUN/'thermal-failure.json',{'reason':reason,'monotonic':time.monotonic()})
    # Best effort minimum frequency; never increase a thermal kernel limit.
    for p in (SYS/'devices/system/cpu/cpufreq').glob('policy*'):
        try:(p/'scaling_max_freq').write_text((p/'cpuinfo_min_freq').read_text())
        except OSError:pass
    libc=ctypes.CDLL(None,use_errno=True)
    if libc.reboot(0x01234567)!=0:raise OSError(ctypes.get_errno(),'Cold reboot failed')

def samples():
    found={};all_values={}
    for zone in (SYS/'class/thermal').glob('thermal_zone*'):
        name=(zone/'type').read_text().strip()
        try:value=int((zone/'temp').read_text())
        except (OSError,ValueError):
            if name in EXPECTED|GPU_EXPECTED:raise RuntimeError('Unreadable CPU/GPU sensor '+name)
            continue
        if name in EXPECTED:
            if not 0<=value<=130000:raise RuntimeError('Invalid CPU sensor '+name)
            found[name]=value
        if name in GPU_EXPECTED and not 0<=value<=130000:raise RuntimeError('Invalid GPU sensor '+name)
        if 0<=value<=130000:all_values[name]=value
    if set(found)!=EXPECTED:raise RuntimeError('Missing CPU sensors: '+','.join(sorted(EXPECTED-set(found))))
    if not GPU_EXPECTED<=all_values.keys():raise RuntimeError('Missing GPU thermal sensors')
    return found,all_values

def policy_info(p):
    fields={name:(p/name).read_text().strip() for name in ['scaling_driver','scaling_governor','related_cpus','scaling_available_frequencies','cpuinfo_min_freq','cpuinfo_max_freq','scaling_min_freq','scaling_max_freq','scaling_cur_freq']}
    if fields['scaling_driver']!='scmi':raise RuntimeError('Unexpected DVFS driver '+fields['scaling_driver'])
    return fields

def set_cap(p,level):
    available=[int(v) for v in (p/'scaling_available_frequencies').read_text().split()]
    target={'normal':1500000,'warm':max(1000000,min(available)),'minimum':min(available)}[level]
    cap=choose_cap(available,target)
    minimum=min(available)
    (p/'scaling_min_freq').write_text(str(minimum))
    (p/'scaling_max_freq').write_text(str(cap))
    (p/'scaling_governor').write_text('schedutil')
    info=policy_info(p)
    if info['scaling_governor']!='schedutil' or int(info['scaling_max_freq'])>cap:raise RuntimeError('CPU frequency cap readback failed')
    return info

def cooling():
    devices=[]
    for c in (SYS/'class/thermal').glob('cooling_device*'):
        name=(c/'type').read_text().strip()
        if 'cpufreq' in name:
            state=int((c/'max_state').read_text())
            if state<=0:raise RuntimeError('CPU cooling has no throttle states')
            devices.append({'name':c.name,'type':name,'max_state':state,'cur_state':int((c/'cur_state').read_text())})
    if len(devices)<2:raise RuntimeError('Both CPU frequency cooling devices are required')
    mapped=set()
    for z in (SYS/'class/thermal').glob('thermal_zone*'):
        if (z/'type').read_text().strip() in EXPECTED:
            if not any(n.is_symlink() for n in z.glob('cdev[0-9]*')):raise RuntimeError('CPU sensor has no cooling binding: '+z.name)
            mapped.add((z/'type').read_text().strip())
    if mapped!=EXPECTED:raise RuntimeError('Incomplete thermal zone bindings')
    return devices

def heartbeat(state):
    atomic_json(RUN/'thermal-state.json',dict(state,monotonic=time.monotonic()))

def main():
    RUN.mkdir(exist_ok=True)
    (RUN/'thermal-ready').unlink(missing_ok=True)
    heartbeat({'phase':'starting'})
    for name in ['qcom_tsens','qcom-spmi-temp-alarm']:
        r=subprocess.run(['/usr/bin/insmod','/thermal-modules/'+name+'.ko'],capture_output=True,text=True,timeout=10)
        print(name,r.returncode,r.stderr.strip(),flush=True)
    deadline=time.monotonic()+55;last='initializing'
    while time.monotonic()<deadline:
        try:
            cpu,all_values=samples()
            if max(cpu.values())>=70000:raise RuntimeError('CPU already warm at startup')
            p0=SYS/'devices/system/cpu/cpufreq/policy0'
            set_cap(p0,'normal')
            # Bring prime policy up only after CPU0 is capped and all sensors read.
            prime=SYS/'devices/system/cpu/cpu6/online'
            if prime.read_text().strip()!='1':prime.write_text('1')
            policies=list((SYS/'devices/system/cpu/cpufreq').glob('policy*'))
            if {p.name for p in policies}!={'policy0','policy6'}:raise RuntimeError('Waiting for both CPU performance policies')
            for p in policies:set_cap(p,'normal')
            cooling()
            for i in [1,2,3,4,5,7]:(SYS/f'devices/system/cpu/cpu{i}/online').write_text('1')
            if (SYS/'devices/system/cpu/online').read_text().strip()!='0-7':raise RuntimeError('All eight CPUs did not come online')
            break
        except (OSError,ValueError,RuntimeError) as e:
            last=str(e);heartbeat({'phase':'initializing','reason':last});time.sleep(.5)
    else:reboot('Thermal startup failed: '+last);return
    level='normal';previous_log=0;overclock_since=None
    while True:
        cpu,all_values=samples();peak=max(cpu.values());level=next_level(max(all_values.values()),level)
        # GPU/SoC sensors also trigger recovery; they are not battery/skin sensors.
        if max(all_values.values())>=85000:reboot('SoC/PMIC temperature >=85 C');return
        if level=='reboot':reboot('CPU temperature >=85 C');return
        policies=list((SYS/'devices/system/cpu/cpufreq').glob('policy*'))
        if {p.name for p in policies}!={'policy0','policy6'}:raise RuntimeError('CPU performance policy disappeared')
        status={p.name:set_cap(p,level) for p in policies}
        if any(int(p['scaling_cur_freq'])>int(p['scaling_max_freq']) for p in status.values()):
            if overclock_since is None:overclock_since=time.monotonic()
            if time.monotonic()-overclock_since>3:raise RuntimeError('CPU clock exceeded requested ceiling for3s')
        else:overclock_since=None
        state={'phase':'ready','level':level,'peak_cpu_millicelsius':peak,'sensors':all_values,'policies':status,'cooling':cooling(),'online':(SYS/'devices/system/cpu/online').read_text().strip(),'battery_skin_protection_verified':False}
        heartbeat(state)
        (RUN/'thermal-ready').touch()
        if time.monotonic()-previous_log>10:print(json.dumps(state),flush=True);previous_log=time.monotonic()
        time.sleep(.5)

if __name__=='__main__':
    try:main()
    except Exception as e:reboot(type(e).__name__+': '+str(e))
