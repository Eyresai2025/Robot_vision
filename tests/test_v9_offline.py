"""Run: python -m unittest discover -s tests -v (no Qt or hardware needed)."""
import tempfile
import unittest
from pathlib import Path
from core import camera_profiles as cp

class Profiles(unittest.TestCase):
    def complete(self):
        p=cp.default_profile()
        p.update({'exposure_us':'100','frame_lines':'8192','line_rate_hz':'5000'})
        return p
    def test_software_only_default(self):
        p=self.complete()
        self.assertEqual(cp.profile_checks(p),[])
        self.assertEqual(p['trigger'],'SOFTWARE_START')
        self.assertEqual(p['line_source'],'INTERNAL_TIMED')
    def test_legacy_encoder_removed(self):
        p=cp.normalize_profile({'trigger':'SPINDLE_ENCODER'})
        self.assertEqual(p['trigger'],'SOFTWARE_START')
        self.assertEqual(p['capture_mode'],'MANUAL_SOFTWARE')
    def test_rpm_not_used_as_line_rate(self):
        p=self.complete();p['line_rate_hz']=''
        self.assertTrue(cp.profile_checks(p))
    def test_reject_exposure_longer_than_line_period(self):
        p=self.complete();p['exposure_us']='400';p['line_rate_hz']='5000'
        self.assertTrue(any('Exposure' in e for e in cp.profile_checks(p)))
    def test_robot_ready_requires_two_vars(self):
        p=self.complete();p['capture_mode']='ROBOT_READY_SOFTWARE'
        self.assertTrue(cp.profile_checks(p))
        p['ready_variable']='B013';p['checkpoint_variable']='I011'
        self.assertEqual(cp.profile_checks(p),[])
    def test_fail_closed_ready_gate(self):
        kwargs={'robot_connected':True,'sample_fresh':True,'value':1,'checkpoint_ok':True,'rising_edge':True}
        self.assertTrue(cp.apply_ready_gate('ROBOT_READY_SOFTWARE',**kwargs)[0])
        for false_field in ('robot_connected','sample_fresh','checkpoint_ok','rising_edge'):
            d=dict(kwargs);d[false_field]=False
            self.assertFalse(cp.apply_ready_gate('ROBOT_READY_SOFTWARE',**d)[0])
        kwargs['value']=0
        self.assertFalse(cp.apply_ready_gate('ROBOT_READY_SOFTWARE',**kwargs)[0])
    def test_json_snapshot(self):
        profiles={v:self.complete() for v in cp.VIEWS}
        with tempfile.TemporaryDirectory() as root:
            dest=cp.export_snapshot({'sku':'CEAT_TEST','version':4,'status':'DRAFT','recipe':{'camera_profiles':profiles}},root)
            doc=cp.load_snapshot(dest,sku='CEAT_TEST',version=4)
            self.assertEqual(doc['profiles']['bead']['line_rate_hz'],'5000')
            with self.assertRaises(ValueError):cp.load_snapshot(dest,sku='WRONG')
    def test_two_cameras_five_views(self):
        self.assertEqual(sum(cp.CAMERAS[v]=='camera_1' for v in cp.VIEWS),2)
        self.assertEqual(sum(cp.CAMERAS[v]=='camera_2' for v in cp.VIEWS),3)
if __name__=='__main__':unittest.main()
