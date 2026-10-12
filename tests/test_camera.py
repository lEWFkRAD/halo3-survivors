import unittest
from hsc_vm import VM
class CameraTests(unittest.TestCase):
    def setUp(self):
        self.v=VM();self.v.boot();self.v.calls.clear()
        self.v.camera_distances={'sv_view_0':5.,'sv_view_1':1.,'sv_view_2':2.}
    def pans(self):return [args for name,args in self.v.calls if name=='camera_set']
    def test_tracks_nearest_anchor(self):
        self.v.run('sv_view_clock');self.assertEqual(self.pans(),[['sv_view_1',6]])
        self.v.camera_distances['sv_view_2']=.5
        self.v.run('sv_view_clock');self.assertEqual(self.pans()[-1],['sv_view_2',6])
    def test_does_not_restart_same_pan(self):
        self.v.run('sv_view_clock');self.v.run('sv_view_clock');self.assertEqual(len(self.pans()),1)
    def test_missing_player_does_not_pan(self):
        self.v.player_count=0;self.v.run('sv_view_clock');self.assertEqual(self.pans(),[])
    def test_finished_run_freezes_camera(self):
        self.v.globals['sv_finished']=True;self.v.run('sv_view_clock');self.assertEqual(self.pans(),[])
