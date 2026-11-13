import unittest
from core import camera_profiles
from core.software_ffc import from_camera_profile,correct_image_with_software_ffc
import numpy as np

class TestFFC(unittest.TestCase):
    def test_default_has_no_external_reference(self):
        p=camera_profiles.default_profile()
        self.assertEqual(p['ffc_mode'],'SOFTWARE')
        self.assertNotIn('ffc_reference',p)
        self.assertEqual(from_camera_profile(p).target_mode,'PERCENTILE_95')
    def test_column_correction_matches(self):
        a=np.array([[20,40,80],[20,40,80]],dtype=np.uint8)
        result,stats=correct_image_with_software_ffc(a,from_camera_profile(camera_profiles.default_profile()))
        self.assertIs(result,a)
        self.assertEqual(a[0].tolist(),[76,76,80])
        self.assertTrue(stats['enabled'])
    def test_legacy_reference_mode_migrates(self):
        p=camera_profiles.normalize_profile({'ffc_mode':'SOFTWARE_REFERENCE'})
        self.assertEqual(p['ffc_mode'],'SOFTWARE')
    def test_disabled_unchanged(self):
        p=camera_profiles.default_profile();p['ffc_mode']='OFF'
        a=np.ones((4,4),dtype=np.uint8)*30
        _,stats=correct_image_with_software_ffc(a,from_camera_profile(p))
        self.assertFalse(stats['enabled']);self.assertTrue((a==30).all())
if __name__=='__main__':unittest.main()
