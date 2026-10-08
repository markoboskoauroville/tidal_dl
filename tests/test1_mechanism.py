"""TEST 1 - THE MECHANISM, ALONE: pure functions, no terminal, no network."""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Sandbox, import_tidaldl, ROOT

REAL_LIKE = '''[downloads]
folder = "/old"

[qobuz]
quality = 3

[tidal]
# 0: 256kbps AAC, 1: 320kbps AAC, 2: 16/44.1 "HiFi" FLAC, 3: 24/44.1 "MQA" FLAC
quality = 3
download_videos = true
user_id = ""
access_token = ""
token_expiry = ""

[deezer]
quality = 1
download_videos = true

[filepaths]
folder_format = "{albumartist} - {title} ({year}) [{container}]"
track_format = "{tracknumber:02}. {artist} - {title}{explicit}"
'''

class Mechanism(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sb = Sandbox()
        cls.t = import_tidaldl(cls.sb)
    @classmethod
    def tearDownClass(cls):
        cls.sb.cleanup()

    def test_url_cleaning(self):
        c = self.t.clean_tidal_url
        self.assertEqual(c("https://listen.tidal.com/browse/album/12345/u"), "https://tidal.com/album/12345")
        self.assertEqual(c("https://tidal.com/browse/track/99?u"), "https://tidal.com/track/99")
        self.assertEqual(c("HTTPS://WWW.TIDAL.COM/Playlist/ab12-cd34-ef56"), "https://tidal.com/playlist/ab12-cd34-ef56")
        self.assertEqual(c("https://tidal.com/artist/7"), "https://tidal.com/artist/7")
        for bad in ("", None, "hello", "https://youtube.com/watch?v=1", "tidal.com/album/"):
            self.assertIsNone(c(bad), bad)

    def test_extract_url_from_noise(self):
        e = self.t.extract_tidal_url
        self.assertEqual(e("check this out https://tidal.com/browse/album/42/u thanks"), "https://tidal.com/album/42")
        self.assertIsNone(e("nothing here"))

    def test_durations(self):
        f = self.t.fmt_dur
        self.assertEqual((f(0), f(9), f(59), f(60), f(125)), ("0s", "9s", "59s", "1m00s", "2m05s"))

    def test_token_remaining(self):
        self.assertGreater(self.t.token_remaining(), 4 * 86400)
        self.assertTrue(self.t.has_token())

    def test_streamrip_patch_changes_only_tidal_and_paths(self):
        new, rep = self.t.patch_streamrip_config(REAL_LIKE, "/dl")
        self.assertIn('folder = "/dl"', new)
        self.assertIn('folder_format = "{albumartist} - {title} ({year})"', new)
        self.assertIn('track_format = "{tracknumber:02}. {artist} - {title}"', new)
        tidal = new.split("[tidal]")[1].split("[deezer]")[0]
        self.assertIn("quality = 2", tidal)
        self.assertIn("download_videos = false", tidal)
        self.assertIn("quality = 3", new.split("[qobuz]")[1].split("[tidal]")[0])      # untouched
        self.assertIn("download_videos = true", new.split("[deezer]")[1].split("[filepaths]")[0])
        again, _ = self.t.patch_streamrip_config(new, "/dl")
        self.assertEqual(new, again, "patching must be idempotent")

    def test_streamrip_patch_adds_missing_keys(self):
        new, _ = self.t.patch_streamrip_config("[tidal]\nuser_id = \"\"\n", "/dl")
        self.assertIn("quality = 2", new)
        self.assertIn("download_videos = false", new)

    def test_validate_download(self):
        with open(os.path.join(ROOT, "tidaldl.py")) as fh:
            good = fh.read()
        v = self.t.validate_download
        self.assertIsNone(v(good))
        self.assertIn("too small", v("#!/usr/bin/env python3\nprint(1)\n"))
        self.assertIn("shebang", v("<html>" + "x" * 20000))
        self.assertIn("cut short", v(good.replace("# end of tidaldl", "")))
        self.assertIn("parse", v(good.replace("def main():", "def main(:", 1)))
        self.assertEqual(self.t.remote_version("x\nVERSION = 7\ny"), 7)
        self.assertIsNone(self.t.remote_version("no version"))

    def test_platform_paths(self):
        t = self.t
        t.IS_MAC, t.IS_TERMUX = True, False
        self.assertTrue(t.default_config_path().endswith("Library/Application Support/streamrip/config.toml"))
        self.assertTrue(t.default_download_dir().endswith("Downloads/tidaldl"))
        t.IS_MAC = False
        os.environ.pop("XDG_CONFIG_HOME", None)
        self.assertTrue(t.default_config_path().endswith(".config/streamrip/config.toml"))
        t.IS_TERMUX = True
        home = os.path.join(self.sb.dir, "th")
        os.makedirs(os.path.join(home, "storage", "downloads"))
        old = os.environ["HOME"]; os.environ["HOME"] = home
        try:
            self.assertEqual(t.default_download_dir(), os.path.join(home, "storage", "downloads", "tidaldl"))
            os.rmdir(os.path.join(home, "storage", "downloads"))
            self.assertEqual(t.default_download_dir(), os.path.join(home, "tidaldl"))
        finally:
            os.environ["HOME"] = old

    def test_history_roundtrip_and_old_format(self):
        t = self.t
        t.append_history("https://tidal.com/album/1", 2, 12.4, True, "/a/b/c.flac")
        with open(t.HISTORY_FILE, "a") as f:     # v21-era 5 field line
            f.write("2026-01-01 10:00\tok\t2\t30\thttps://tidal.com/album/2\n")
        rows = t.load_history()
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(len(r) == 6 for r in rows))

    def test_promote_flac_picks_only_real_flac(self):
        import subprocess, shutil
        sb, t = self.sb, self.t
        stage = os.path.join(sb.dir, "stage"); out = os.path.join(sb.dir, "out")
        d = os.path.join(stage, "A - B (2020)"); os.makedirs(d)
        def mk(name, codec):
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=duration=1",
                            "-c:a", codec, os.path.join(d, name)], check=True)
        mk("01.flac", "flac"); mk("02.m4a", "aac")
        # a FLAC-named file that is really AAC must still be refused
        mk("03.m4a", "aac"); os.rename(os.path.join(d, "03.m4a"), os.path.join(d, "03.flac"))
        saved, n, rejected = t.promote_flac(stage, out)
        self.assertEqual(n, 1)
        self.assertTrue(saved.endswith("01.flac"))
        self.assertEqual(sorted(os.listdir(os.path.join(out, "A - B (2020)"))), ["01.flac"])
        self.assertEqual(len(rejected), 2)
        shutil.rmtree(stage); shutil.rmtree(out)

if __name__ == "__main__":
    unittest.main(verbosity=2)
