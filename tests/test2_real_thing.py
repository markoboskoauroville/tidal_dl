"""TEST 2 - THE REAL THING, ONCE: the real TUI on a real pty, a pasted link,
a download through the (fake) rip, a verified FLAC on disk, then quit."""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Sandbox, start_tidaldl

class RealThing(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
    def tearDown(self):
        self.sb.cleanup()

    def test_paste_download_verify_quit(self):
        p = start_tidaldl(self.sb, FAKE_RIP_MODE="flac")
        try:
            p.expect("PASTE TIDAL LINK")
            p.expect("waiting for paste...")
            p.send("https://listen.tidal.com/browse/album/777/u")        # one burst = a paste
            p.expect("starting in")
            p.send(" ")                                                    # start now
            p.expect("verified real FLAC")
            p.expect("holding 11s")
            p.send("x")                                                    # leave the hold screen
            p.expect("recent downloads")
            p.send("q")
            self.assertEqual(p.wait_exit(), 0)
        finally:
            p.kill()
        files = self.sb.audio_files()
        self.assertEqual(len(files), 1, files)
        self.assertTrue(files[0].endswith("Test Artist - Test Album (2020)/01. Test Artist - Song 1.flac"), files)
        self.assertTrue(os.path.exists(os.path.join(self.sb.dl, "Test Artist - Test Album (2020)", "cover.jpg")))
        with open(self.sb.riplog) as f:
            call = f.read()
        self.assertIn("--quality 2", call)
        self.assertIn("url https://tidal.com/album/777", call)          # /u and browse stripped
        self.assertEqual(self.sb.staging_leftovers(), [])
        with open(os.path.join(self.sb.prefs, "history")) as f:
            self.assertIn("\tok\t2\t", f.read())

    def test_version_and_help_screens(self):
        p = start_tidaldl(self.sb)
        try:
            p.expect("v22")
            p.send("h")
            p.expect("FLAC safety")
            p.send("x")
            p.expect("update")
            p.send("q")
            self.assertEqual(p.wait_exit(), 0)
        finally:
            p.kill()

    def test_command_line_link(self):
        p = start_tidaldl(self.sb, "https://tidal.com/track/5", FAKE_RIP_MODE="flac")
        try:
            p.expect("verified real FLAC")
            p.send("x")
            self.assertEqual(p.wait_exit(timeout=20), 0)
        finally:
            p.kill()
        self.assertEqual(len(self.sb.audio_files()), 1)

if __name__ == "__main__":
    unittest.main(verbosity=2)
