#!/usr/bin/python
"""Independent monotonic heartbeat monitor; no storage access."""
import importlib.util,json,time
from pathlib import Path
spec=importlib.util.spec_from_file_location('guard','/thermal-guard.py');guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
start=time.monotonic()
while True:
    try:
        state=json.loads(Path('/run/thermal-state.json').read_text())
        if time.monotonic()-state['monotonic']>12:guard.reboot('Thermal monitor heartbeat stopped')
    except (OSError,ValueError,KeyError):
        if time.monotonic()-start>15:guard.reboot('Thermal monitor did not start')
    time.sleep(1)
