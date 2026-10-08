"""Shared helpers: a sandbox HOME, a fake `rip` that writes real FLAC/AAC with
ffmpeg, and a pty driver that runs the real tidaldl TUI."""
import os, pty, re, select, shutil, signal, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TIDALDL = os.path.join(ROOT, "tidaldl.py")
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

FAKE_RIP = r'''#!__PY__
# fake streamrip: FAKE_RIP_MODE = flac | aac | mixed | fail | none
import os, subprocess, sys
a = sys.argv[1:]
folder = a[a.index("--folder") + 1]
mode = os.environ.get("FAKE_RIP_MODE", "flac")
with open(os.environ["FAKE_RIP_LOG"], "a") as f:
    f.write(" ".join(a) + "\n")
if mode == "fail":
    print("fake rip: boom"); sys.exit(1)
if mode == "none":
    sys.exit(0)
d = os.path.join(folder, "Test Artist - Test Album (2020)")
os.makedirs(d, exist_ok=True)
def make(name, codec):
    out = os.path.join(d, name)
    args = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=1"]
    args += ["-c:a", "flac"] if codec == "flac" else ["-c:a", "aac"]
    subprocess.run(args + [out], check=True)
kinds = {"flac": ["flac"], "aac": ["aac"], "mixed": ["flac", "aac", "flac"]}[mode]
for i, k in enumerate(kinds, 1):
    make("%02d. Test Artist - Song %d.%s" % (i, i, "flac" if k == "flac" else "m4a"), k)
open(os.path.join(d, "cover.jpg"), "wb").write(b"\xff\xd8fake")
print("fake rip: downloaded", len(kinds), "file(s)")
'''

class Sandbox:
    """A throwaway HOME with a logged-in streamrip config and a fake rip on PATH."""
    def __init__(self, logged_in=True, with_ffprobe=True):
        self.dir = tempfile.mkdtemp(prefix="tidaldl_test_")
        d = self.dir
        self.home = os.path.join(d, "home")
        self.bin = os.path.join(d, "bin")
        self.dl = os.path.join(d, "Downloads", "tidaldl")
        self.prefs = os.path.join(d, "prefs")
        self.tmp = os.path.join(d, "tmp")
        self.config = os.path.join(d, "streamrip", "config.toml")
        self.riplog = os.path.join(d, "rip.log")
        for p in (self.home, self.bin, self.tmp, os.path.dirname(self.config)):
            os.makedirs(p)
        rip = os.path.join(self.bin, "rip")
        with open(rip, "w") as f:
            f.write(FAKE_RIP.replace("__PY__", sys.executable))
        os.chmod(rip, 0o755)
        for tool in ("ffmpeg", "ffprobe") if with_ffprobe else ("ffmpeg",):
            os.symlink(shutil.which(tool), os.path.join(self.bin, tool))
        expiry = time.time() + 5 * 86400 if logged_in else ""
        tok = "tok" if logged_in else ""
        with open(self.config, "w") as f:
            f.write('[downloads]\nfolder = "x"\n\n[tidal]\nquality = 2\n'
                    f'access_token = "{tok}"\nrefresh_token = "{tok}"\n'
                    f'token_expiry = "{expiry}"\nuser_id = "1"\ncountry_code = "HR"\n')

    def env(self, **extra):
        e = {"PATH": self.bin + ":/usr/bin:/bin", "HOME": self.home, "TERM": "xterm-256color",
             "TIDALDL_CONFIG": self.config, "TIDALDL_DIR": self.dl, "TIDALDL_PREFS": self.prefs,
             "TMPDIR": self.tmp, "FAKE_RIP_LOG": self.riplog, "LANG": "C.UTF-8"}
        e.update(extra)
        return e

    def staging_leftovers(self):
        return [n for n in os.listdir(self.tmp) if n.startswith("tidaldl_stage_")]

    def audio_files(self):
        out = []
        for dp, _, fs in os.walk(self.dl):
            out += [os.path.join(dp, f) for f in fs if f.endswith((".flac", ".m4a"))]
        return sorted(out)

    def cleanup(self):
        shutil.rmtree(self.dir, ignore_errors=True)

class Pty:
    """Run a command on a pty; expect() waits for text with ANSI stripped."""
    def __init__(self, argv, env, cwd=None):
        self.pid, self.fd = pty.fork()
        if self.pid == 0:
            if cwd:
                os.chdir(cwd)
            os.execve(argv[0], argv, env)
        self.buf = ""
        self.raw = ""
        import fcntl, struct, termios
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, struct.pack("HHHH", 50, 160, 0, 0))

    def _pump(self, timeout):
        r, _, _ = select.select([self.fd], [], [], timeout)
        if not r:
            return False
        try:
            data = os.read(self.fd, 65536)
        except OSError:
            return False
        if not data:
            return False
        txt = data.decode("utf-8", "ignore")
        self.raw += txt
        self.buf += ANSI.sub("", txt)
        return True

    def expect(self, text, timeout=20):
        end = time.time() + timeout
        while time.time() < end:
            if text in self.buf:
                i = self.buf.index(text) + len(text)
                seen, self.buf = self.buf[:i], self.buf[i:]
                return seen
            self._pump(0.2)
        raise AssertionError("timeout waiting for %r; screen tail: %r" % (text, self.buf[-600:]))

    def send(self, s):
        os.write(self.fd, s.encode())

    def wait_exit(self, timeout=15):
        end = time.time() + timeout
        while time.time() < end:
            try:
                pid, status = os.waitpid(self.pid, os.WNOHANG)
            except ChildProcessError:
                return 0
            if pid:
                return os.waitstatus_to_exitcode(status)
            self._pump(0.1)
        os.kill(self.pid, signal.SIGKILL)
        raise AssertionError("process did not exit")

    def kill(self):
        try:
            os.kill(self.pid, signal.SIGKILL)
            os.waitpid(self.pid, 0)
        except (OSError, ChildProcessError):
            pass

def start_tidaldl(sb, *args, **env):
    return Pty([sys.executable, TIDALDL, *args], sb.env(**env))

def import_tidaldl(sb, **env):
    """Import a fresh copy of tidaldl.py configured for the sandbox."""
    import importlib.util
    for k, v in sb.env(**env).items():
        os.environ[k] = v
    spec = importlib.util.spec_from_file_location("tidaldl_under_test", TIDALDL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
