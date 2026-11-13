import importlib.util,unittest,tempfile
from pathlib import Path
s=importlib.util.spec_from_file_location('guard',Path(__file__).with_name('thermal-guard.py'));g=importlib.util.module_from_spec(s);s.loader.exec_module(g)
class ThermalPolicy(unittest.TestCase):
 def test_escalation(self):
  self.assertEqual([g.next_level(t,'normal') for t in [40000,69999,70000,79999,80000,84999,85000]],['normal','normal','warm','warm','minimum','minimum','reboot'])
 def test_recovery_hysteresis(self):
  self.assertEqual(g.next_level(79000,'minimum'),'minimum');self.assertEqual(g.next_level(74999,'minimum'),'warm');self.assertEqual(g.next_level(66000,'warm'),'warm');self.assertEqual(g.next_level(64999,'warm'),'normal')
 def test_invalid_data(self):
  for t in [-1,130001]:
   with self.assertRaises(ValueError):g.next_level(t,'normal')
 def test_round_down_firmware_caps(self):
  self.assertEqual(g.choose_cap([600000,1036800,1497600,2016000],1500000),1497600)
  with self.assertRaises(ValueError):g.choose_cap([1800000],1500000)
 def test_sensor_failure_blocks_startup(self):
  old=g.SYS
  try:
   with tempfile.TemporaryDirectory() as tmp:
    g.SYS=Path(tmp);z=g.SYS/'class/thermal/thermal_zone0';z.mkdir(parents=True);(z/'type').write_text('cpu-0-0-0-thermal');(z/'temp').write_text('45000')
    with self.assertRaisesRegex(RuntimeError,'Missing CPU sensors'):g.samples()
    (z/'temp').write_text('-1000')
    with self.assertRaisesRegex(RuntimeError,'Invalid CPU sensor'):g.samples()
  finally:g.SYS=old
 def test_cpu_caps_and_governor(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)
   fields={'scaling_driver':'scmi','scaling_governor':'performance','related_cpus':'0 1 2 3 4 5','scaling_available_frequencies':'600000 1036800 1497600 2016000','cpuinfo_min_freq':'600000','cpuinfo_max_freq':'2016000','scaling_min_freq':'600000','scaling_max_freq':'2016000','scaling_cur_freq':'600000'}
   for name,value in fields.items():(p/name).write_text(value)
   self.assertEqual(g.set_cap(p,'normal')['scaling_max_freq'],'1497600');self.assertEqual((p/'scaling_governor').read_text(),'schedutil')
   self.assertEqual(g.set_cap(p,'warm')['scaling_max_freq'],'600000');self.assertEqual(g.set_cap(p,'minimum')['scaling_max_freq'],'600000')
 def test_prime_minimum_above_one_ghz(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)
   fields={'scaling_driver':'scmi','scaling_governor':'performance','related_cpus':'6 7','scaling_available_frequencies':'1017600 1209600 1401600 1689600','cpuinfo_min_freq':'1017600','cpuinfo_max_freq':'1689600','scaling_min_freq':'1017600','scaling_max_freq':'1689600','scaling_cur_freq':'1017600'}
   for name,value in fields.items():(p/name).write_text(value)
   self.assertEqual(g.set_cap(p,'normal')['scaling_max_freq'],'1401600');self.assertEqual(g.set_cap(p,'warm')['scaling_max_freq'],'1017600');self.assertEqual(g.set_cap(p,'minimum')['scaling_max_freq'],'1017600')
 def test_sensor_layout(self):self.assertEqual(len(g.EXPECTED),16)
if __name__=='__main__':unittest.main()
