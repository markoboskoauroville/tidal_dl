"""TEST 3 - THE UGLY CASES: the world misbehaving. TIDAL serves AAC instead of
FLAC, one track of an album falls back, rip fails or produces nothing, no login,
no ffprobe, garbage pasted, the update server gone or serving half a file."""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Sandbox, start_tidaldl, ROOT

def run_cli(sb, url="https://tidal.com/album/1", **env):
    p = start_tidaldl(sb, url, **env)
    try:
        out = p.expect("holding 11s", timeout=30)
        p.send("x")
        p.wait_exit(timeout=20)
        return out
    finally:
        p.kill()

class Ugly(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
    def tearDown(self):
        self.sb.cleanup()

    def test_aac_fallback_saves_nothing_and_touches_nothing(self):
        existing = os.path.join(self.sb.dl, "Test Artist - Test Album (2020)")
        os.makedirs(existing)
        keep = os.path.join(existing, "01. Test Artist - Song 1.flac")
        with open(keep, "wb") as f:
            f.write(b"PRECIOUS")
        out = run_cli(self.sb, FAKE_RIP_MODE="aac")
        self.assertIn("FLAC not available for this track", out)
        with open(keep, "rb") as f:
            self.assertEqual(f.read(), b"PRECIOUS")
        self.assertEqual([x for x in self.sb.audio_files() if x.endswith(".m4a")], [])
        self.assertEqual(self.sb.staging_leftovers(), [])

    def test_mixed_album_keeps_only_real_flac(self):
        out = run_cli(self.sb, FAKE_RIP_MODE="mixed")
        files = [os.path.basename(x) for x in self.sb.audio_files()]
        self.assertEqual(files, ["01. Test Artist - Song 1.flac", "03. Test Artist - Song 3.flac"])
        self.assertIn("verified real FLAC (2 files)", out)
        self.assertIn("1 track(s) came back as aac", out)

    def test_rip_failure_is_reported_and_logged(self):
        out = run_cli(self.sb, FAKE_RIP_MODE="fail")
        self.assertIn("failed (exit 1)", out)
        self.assertEqual(self.sb.audio_files(), [])
        self.assertEqual(self.sb.staging_leftovers(), [])
        with open(os.path.join(self.sb.prefs, "history")) as f:
            self.assertIn("\tfail\t", f.read())

    def test_rip_succeeds_but_produces_nothing(self):
        out = run_cli(self.sb, FAKE_RIP_MODE="none")
        self.assertIn("nothing was produced", out)
        self.assertEqual(self.sb.audio_files(), [])

    def test_no_ffprobe_trusts_the_extension(self):
        sb = Sandbox(with_ffprobe=False)
        try:
            # PATH has only the sandbox bin, so ffprobe really is absent
            out = run_cli(sb, FAKE_RIP_MODE="flac", PATH=sb.bin)
            self.assertIn("verified real FLAC", out)
            self.assertEqual(len(sb.audio_files()), 1)
        finally:
            sb.cleanup()

    def test_not_logged_in_prints_login_command_and_downloads_nothing(self):
        sb = Sandbox(logged_in=False)
        try:
            p = start_tidaldl(sb, "https://tidal.com/album/1")
            out = p.expect("Then run tidaldl again.")
            self.assertIn("No valid TIDAL login found", out)
            self.assertIn("search --first tidal track", p.buf + out)
            p.wait_exit()
            self.assertFalse(os.path.exists(sb.riplog))
        finally:
            p.kill(); sb.cleanup()

    def test_garbage_paste_and_bad_cli_arg(self):
        p = start_tidaldl(self.sb)
        try:
            p.expect("waiting for paste")
            p.send("https://example.com/not-tidal-at-all")
            p.expect("not a tidal link")
            p.send("q")                     # clears the pasted text
            p.expect("waiting for paste")
            p.send("q")
            self.assertEqual(p.wait_exit(), 0)
        finally:
            p.kill()
        p = start_tidaldl(self.sb, "garbage")
        try:
            p.expect("Not a valid TIDAL link")
            p.wait_exit()
        finally:
            p.kill()
        self.assertFalse(os.path.exists(self.sb.riplog))

    def test_cancel_during_countdown(self):
        p = start_tidaldl(self.sb, FAKE_RIP_MODE="flac")
        try:
            p.expect("waiting for paste")
            p.send("https://tidal.com/album/9")
            p.expect("starting in")
            p.send("q")
            p.expect("cancelled")
            p.send("q")
            p.wait_exit()
        finally:
            p.kill()
        self.assertFalse(os.path.exists(self.sb.riplog))

    def _update_screen(self, url):
        p = start_tidaldl(self.sb, TIDALDL_UPDATE_URL=url)
        p.expect("waiting for paste")
        p.send("u")
        return p

    def test_update_server_unreachable_changes_nothing(self):
        p = self._update_screen("file:///nonexistent/tidaldl.py")
        try:
            p.expect("nothing was changed")
            p.send("x")
            p.expect("update check failed")
            p.send("q"); p.wait_exit()
        finally:
            p.kill()

    def test_truncated_update_is_refused(self):
        with open(os.path.join(ROOT, "tidaldl.py")) as f:
            full = f.read()
        half = full[: len(full) // 2].replace("VERSION = 22", "VERSION = 99")
        path = os.path.join(self.sb.dir, "half.py")
        with open(path, "w") as f:
            f.write(half)
        p = self._update_screen("file://" + path)
        try:
            p.expect("v22 -> available v99")
            p.expect("not usable")
            p.send("x")
            p.expect("update refused")
            p.send("q"); p.wait_exit()
        finally:
            p.kill()

if __name__ == "__main__":
    unittest.main(verbosity=2)
