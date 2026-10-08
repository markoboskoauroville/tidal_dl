"""TEST 4 - THE UPGRADE, FROM THE VERSION BEFORE: a machine that ran v21 (the
original installer's command, its prefs, its 5-field history, its patched
streamrip config) then gets v22 - by the U key, and by the generated installers
run twice over the top with the package managers stubbed."""
import os, subprocess, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Sandbox, Pty, start_tidaldl, ROOT, TIDALDL

class Upgrade(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
    def tearDown(self):
        self.sb.cleanup()

    def _old_state(self):
        os.makedirs(self.sb.prefs)
        with open(os.path.join(self.sb.prefs, "prefs"), "w") as f:
            f.write("1")                                    # AAC chosen under v21
        with open(os.path.join(self.sb.prefs, "history"), "w") as f:
            f.write("2026-09-01 10:00\tok\t2\t40\thttps://tidal.com/album/3\n")   # v21: 5 fields

    def test_v22_reads_v21_state(self):
        self._old_state()
        p = start_tidaldl(self.sb)
        try:
            p.expect("320 kbps AAC")
            p.expect("recent downloads")
            p.send("q")
            self.assertEqual(p.wait_exit(), 0)
        finally:
            p.kill()
        self.assertIn("> 320 kbps AAC", p.raw.replace("\x1b[38;5;46m\x1b[1m", ""))   # saved quality kept

    def test_setup_over_v21_patched_config_changes_nothing(self):
        env = self.sb.env()
        with open(self.sb.config, "w") as f:
            f.write('[downloads]\nfolder = "%s"\nfolder_format = "{albumartist} - {title} ({year})"\n'
                    'track_format = "{tracknumber:02}. {artist} - {title}"\n\n[tidal]\nquality = 2\n'
                    'download_videos = false\naccess_token = "keep"\n' % self.sb.dl)
        before = open(self.sb.config).read()
        r = subprocess.run([sys.executable, TIDALDL, "--setup"], env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(open(self.sb.config).read(), before)
        self.assertIn('access_token = "keep"', before)

    def test_u_key_updates_in_place_and_keeps_shebang(self):
        target = os.path.join(self.sb.dir, "bin_installed", "tidaldl")
        os.makedirs(os.path.dirname(target))
        with open(TIDALDL) as f:
            src = f.read()
        installed = "#!%s\n" % sys.executable + src.split("\n", 1)[1]    # a Termux-style shebang
        with open(target, "w") as f:
            f.write(installed)
        os.chmod(target, 0o755)
        newer = src.replace("VERSION = 22", "VERSION = 23")
        npath = os.path.join(self.sb.dir, "v23.py")
        with open(npath, "w") as f:
            f.write(newer)
        p = Pty([target], self.sb.env(TIDALDL_UPDATE_URL="file://" + npath))
        try:
            p.expect("waiting for paste")
            p.send("u")
            p.expect("installed v22 -> available v23")
            p.expect("press y to update")
            p.send("y")
            p.expect("updated to v23")
            p.expect("v23")                       # the restarted program shows its new version
            p.send("q")
            self.assertEqual(p.wait_exit(), 0)
        finally:
            p.kill()
        with open(target) as f:
            text = f.read()
        self.assertTrue(text.startswith("#!%s\n" % sys.executable), "shebang must be preserved")
        self.assertIn("VERSION = 23", text)
        self.assertFalse(os.path.exists(target + ".new"))
        self.assertTrue(os.access(target, os.X_OK))

    def test_u_key_already_current_and_declined(self):
        p = start_tidaldl(self.sb, TIDALDL_UPDATE_URL="file://" + TIDALDL)
        try:
            p.expect("waiting for paste"); p.send("u")
            p.expect("already on the latest"); p.send("x")
            p.expect("v22 is current"); p.send("q"); p.wait_exit()
        finally:
            p.kill()
        newer = open(TIDALDL).read().replace("VERSION = 22", "VERSION = 23")
        npath = os.path.join(self.sb.dir, "v23.py")
        open(npath, "w").write(newer)
        before = open(TIDALDL).read()
        p = start_tidaldl(self.sb, TIDALDL_UPDATE_URL="file://" + npath)
        try:
            p.expect("waiting for paste"); p.send("u")
            p.expect("press y to update"); p.send("n")
            p.expect("update cancelled"); p.send("q"); p.wait_exit()
        finally:
            p.kill()
        self.assertEqual(open(TIDALDL).read(), before)

    # ---- the generated installers, run twice, package managers stubbed ----
    def _stubs(self, extra=""):
        stub = os.path.join(self.sb.dir, "stubs")
        os.makedirs(stub, exist_ok=True)
        def w(name, body):
            p = os.path.join(stub, name)
            with open(p, "w") as f:
                f.write("#!/bin/bash\n" + body + "\n")
            os.chmod(p, 0o755)
        return stub, w

    def _run_installer(self, script, env):
        return subprocess.run(["bash", os.path.join(ROOT, script)], env=env, capture_output=True,
                              text=True, timeout=120)

    def test_macos_installer_twice_over_the_top(self):
        stub, w = self._stubs()
        w("uname", 'case "$1" in -s) echo Darwin;; -m) echo arm64;; *) /usr/bin/uname "$@";; esac')
        w("brew", "echo brew $@ >> $STUBLOG")
        w("pipx", "echo pipx $@ >> $STUBLOG")
        w("curl", "exit 22")
        w("rip", "exit 0")
        w("python3", 'exec %s "$@"' % sys.executable)
        w("ffmpeg", "exit 0")
        log = os.path.join(self.sb.dir, "stub.log")
        env = self.sb.env(STUBLOG=log, PATH=stub + ":/usr/bin:/bin")
        for run in (1, 2):
            r = self._run_installer("install-macos.sh", env)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        cmd = os.path.join(self.sb.home, ".local", "bin", "tidaldl")
        self.assertTrue(os.access(cmd, os.X_OK))
        with open(cmd) as f:
            self.assertIn("VERSION = 22", f.read())
        with open(os.path.join(self.sb.home, ".zshrc")) as f:
            self.assertEqual(f.read().count("added by tidaldl installer"), 1)    # not duplicated on run 2
        self.assertTrue(os.path.isdir(os.path.join(self.sb.home, "Downloads", "tidaldl")))
        with open(self.sb.config) as f:
            self.assertIn("download_videos = false", f.read())
        self.assertFalse(os.path.exists(cmd + ".new"))

    def test_macos_installer_refuses_intel(self):
        stub, w = self._stubs()
        w("uname", 'case "$1" in -s) echo Darwin;; -m) echo x86_64;; esac')
        r = self._run_installer("install-macos.sh", self.sb.env(PATH=stub + ":/usr/bin:/bin"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("Apple Silicon", r.stdout)

    def test_termux_installer_twice_over_the_top(self):
        stub, w = self._stubs()
        prefix = os.path.join(self.sb.dir, "prefix")
        os.makedirs(os.path.join(prefix, "bin"))
        os.symlink(sys.executable, os.path.join(prefix, "bin", "python3"))
        venv = os.path.join(self.sb.home, ".local", "share", "tidaldl", "venv", "bin")
        os.makedirs(venv)
        for n in ("python", "pip", "rip"):
            p = os.path.join(venv, n)
            with open(p, "w") as f:
                f.write("#!/bin/bash\necho %s $@ >> $STUBLOG\n" % n)
            os.chmod(p, 0o755)
        w("pkg", "echo pkg $@ >> $STUBLOG")
        w("curl", "exit 22")
        log = os.path.join(self.sb.dir, "stub.log")
        env = self.sb.env(STUBLOG=log, PREFIX=prefix, TIDALDL_ALLOW_ANY_HOST="1",
                          PATH=stub + ":/usr/bin:/bin")
        for run in (1, 2):
            r = self._run_installer("install-termux.sh", env)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        cmd = os.path.join(prefix, "bin", "tidaldl")
        with open(cmd) as f:
            lines = f.read().split("\n")
        self.assertEqual(lines[0], "#!%s/bin/python3" % prefix)       # Termux shebang, no /usr/bin/env
        self.assertIn("VERSION = 22", "\n".join(lines))
        self.assertTrue(os.path.islink(os.path.join(prefix, "bin", "rip")))
        r = subprocess.run([cmd, "--version"], env=self.sb.env(), capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), "tidaldl v22", r.stderr)
        with open(log) as f:
            self.assertIn("pkg install -y python ffmpeg", f.read())

if __name__ == "__main__":
    unittest.main(verbosity=2)
