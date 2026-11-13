#!/usr/bin/env python3
from pathlib import Path
import os,runpy
os.environ['OP13_THERMAL_BUILD']='1'
runpy.run_path(str(Path(__file__).resolve().parent.parent/'armada-steam-v1/build-media.py'),run_name='__main__')
