"""TEST 5 - TERMUX MODE: the real TUI on a real pty, told it is on Termux
(TERMUX_VERSION set), with NO path overrides, so the app runs its own
IS_TERMUX detection and default_download_dir() exactly as it would on a phone.
A pasted link downloads through the (fake) rip and the verified FLAC must land
in the Termux folder the app chose for itself:

  - termux-setup-storage has been run  -> ~/storage/downloads/tidaldl
  - it has not been run                -> ~/tidaldl

This is Termux *mode* on this machine (detection forced via TERMUX_VERSION), not
a real Android device; see DELIVERY_RECORD.md for what has never run on real
hardware.
"""
import os, sys, time, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Sandbox, Pty, TIDALDL

class TermuxMode(unittest.TestCase):
    def setUp(self):
        # Sandbox gives us a fake `rip` + ffmpeg/ffprobe on PATH and a throwaway home.
        self.sb = Sandbox()
    def tearDown(self):
        self.sb.cleanup()

    def _termux_env(self):
        """Termux-like: TERMUX_VERSION set, and crucially no TIDALDL_CONFIG /
        TIDALDL_DIR, so the app computes the config and download paths itself."""
        return {"PATH": self.sb.bin + ":/usr/bin:/bin", "HOME": self.sb.home,
                "TERM": "xterm-256color", "TMPDIR": self.sb.tmp,
                "FAKE_RIP_LOG": self.sb.riplog, "LANG": "C.UTF-8",
                "TIDALDL_PREFS": self.sb.prefs, "TERMUX_VERSION": "0.118.0",
                "FAKE_RIP_MODE": "flac"}

    def _write_streamrip_config(self):
        """A logged-in streamrip config at the Termux default (~/.config)."""
        cfg = os.path.join(self.sb.home, ".config", "streamrip", "config.toml")
        os.makedirs(os.path.dirname(cfg), exist_ok=True)
        with open(cfg, "w") as f:
            f.write('[downloads]\nfolder = "x"\n\n[tidal]\nquality = 2\n'
                    'access_token = "tok"\nrefresh_token = "tok"\n'
                    f'token_expiry = "{time.time() + 5*86400}"\n'
                    'user_id = "1"\ncountry_code = "HR"\n')

    def _flacs_under(self, root):
        out = []
        for dp, _, fs in os.walk(root):
            out += [os.path.join(dp, f) for f in fs if f.endswith(".flac")]
        return out

    def _paste_download_quit(self):
        p = Pty([sys.executable, TIDALDL], self._termux_env())
        try:
            p.expect("PASTE TIDAL LINK")
            p.expect("long-press, paste")                 # the Termux paste hint, not cmd+v
            p.send("https://listen.tidal.com/browse/album/777/u")
            p.expect("starting in")
            p.send(" ")
            p.expect("verified real FLAC")
            p.send("x")
            p.expect("recent downloads")
            p.send("q")
            self.assertEqual(p.wait_exit(), 0)
        finally:
            p.kill()

    def test_downloads_into_shared_storage_when_set_up(self):
        self._write_streamrip_config()
        os.makedirs(os.path.join(self.sb.home, "storage", "downloads"))
        self._paste_download_quit()
        want = os.path.join(self.sb.home, "storage", "downloads", "tidaldl")
        flacs = self._flacs_under(want)
        self.assertEqual(len(flacs), 1, f"expected one FLAC under {want}, got {flacs}")
        self.assertTrue(flacs[0].endswith(
            "Test Artist - Test Album (2020)/01. Test Artist - Song 1.flac"), flacs)

    def test_downloads_into_home_when_storage_not_set_up(self):
        self._write_streamrip_config()
        # no ~/storage/downloads -> the app must fall back to ~/tidaldl
        self._paste_download_quit()
        want = os.path.join(self.sb.home, "tidaldl")
        self.assertTrue(os.path.isdir(want), f"{want} was not created")
        self.assertEqual(len(self._flacs_under(want)), 1)
        # and it must NOT have used the macOS ~/Downloads/tidaldl path
        self.assertEqual(self._flacs_under(os.path.join(self.sb.home, "Downloads")), [])

if __name__ == "__main__":
    unittest.main(verbosity=2)
