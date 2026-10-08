#!/usr/bin/env python3
# tidaldl: paste a TIDAL link, get verified FLAC. macOS (Apple Silicon) and Termux.
# One source file; the installers are generated from it (tools/build_installers.py).
import sys
import os
import re
import time
import shutil
import tempfile
import termios
import tty
import select
import subprocess

VERSION = 22
REPO = "markoboskoauroville/tidal_dl"
UPDATE_URL = (os.environ.get("TIDALDL_UPDATE_URL")
              or f"https://raw.githubusercontent.com/{REPO}/main/tidaldl.py")

ESC = "\033"
CLEAR = f"{ESC}[2J{ESC}[H"
HIDE = f"{ESC}[?25l"
SHOW = f"{ESC}[?25h"
RESET = f"{ESC}[0m"
BG = f"{ESC}[40m"
CYAN = f"{ESC}[38;5;51m"
GREEN = f"{ESC}[38;5;46m"
YELLOW = f"{ESC}[38;5;226m"
RED = f"{ESC}[38;5;203m"
WHITE = f"{ESC}[38;5;255m"
GREY = f"{ESC}[38;5;245m"
BOLD = f"{ESC}[1m"
CHECK = "\u2713"

def keycap(letter, fg="232", bg="51"):
    return f"{ESC}[48;5;{bg}m{ESC}[38;5;{fg}m {letter} {RESET}"

IS_MAC = sys.platform == "darwin"
IS_TERMUX = ("TERMUX_VERSION" in os.environ
             or os.path.isdir("/data/data/com.termux/files"))

def default_config_path():
    """Where streamrip keeps config.toml (click.get_app_dir on each OS)."""
    if IS_MAC:
        return os.path.expanduser("~/Library/Application Support/streamrip/config.toml")
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "streamrip", "config.toml")

def default_download_dir():
    if IS_TERMUX:
        shared = os.path.expanduser("~/storage/downloads")
        if os.path.isdir(shared):
            return os.path.join(shared, "tidaldl")
        return os.path.expanduser("~/tidaldl")
    return os.path.expanduser("~/Downloads/tidaldl")

if IS_TERMUX:
    # termux-tools ships termux-open-url; lets streamrip's login open a browser
    os.environ.setdefault("BROWSER", "termux-open-url %s")

# env overrides exist for the test-suite and for odd setups
CONFIG = os.environ.get("TIDALDL_CONFIG") or default_config_path()
DOWNLOAD_DIR = os.environ.get("TIDALDL_DIR") or default_download_dir()
PASTE_HINT = "long-press, paste" if IS_TERMUX else "cmd+v"
QUALITIES = [(1, "320 kbps AAC"), (2, "16/44.1 HiFi FLAC")]
QMAP = dict(QUALITIES)
PREFS_DIR = (os.environ.get("TIDALDL_PREFS")
             or os.path.expanduser("~/.config/tidaldl"))
PREFS_FILE = os.path.join(PREFS_DIR, "prefs")
HISTORY_FILE = os.path.join(PREFS_DIR, "history")
DEFAULT_QUALITY = 2
LOGIN_SONG = "Her Majesty Beatles"
COUNTDOWN_SECS = 10
HOLD_SECS = 11

TIDAL_CORE = re.compile(
    r"https?://(?:www\.|listen\.)?tidal\.com/(?:browse/)?"
    r"(album|track|playlist|artist|mix|video)/([0-9a-fA-F\-]+)",
    re.IGNORECASE,
)

def clean_tidal_url(text):
    if not text:
        return None
    m = TIDAL_CORE.search(text)
    if not m:
        return None
    return f"https://tidal.com/{m.group(1).lower()}/{m.group(2)}"

def extract_tidal_url(text):
    for token in text.split():
        u = clean_tidal_url(token)
        if u:
            return u
    return clean_tidal_url(text)

def rip_path():
    return shutil.which("rip") or os.path.expanduser("~/.local/bin/rip")

def login_command():
    return (f'{rip_path()} --folder "{DOWNLOAD_DIR}" --quality 1 '
            f'search --first tidal track "{LOGIN_SONG}"')

def ensure_dirs():
    for d in (DOWNLOAD_DIR, PREFS_DIR):
        try:
            os.makedirs(d, exist_ok=True)
        except OSError:
            pass

def load_quality():
    try:
        with open(PREFS_FILE, "r") as f:
            val = int(f.read().strip())
        if val in QMAP:
            return val
    except (OSError, ValueError):
        pass
    return DEFAULT_QUALITY

def save_quality(q):
    try:
        os.makedirs(PREFS_DIR, exist_ok=True)
        with open(PREFS_FILE, "w") as f:
            f.write(str(q))
    except OSError:
        pass

def append_history(url, quality, secs, ok, path=""):
    try:
        os.makedirs(PREFS_DIR, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d %H:%M")
        flag = "ok" if ok else "fail"
        safe_path = (path or "").replace("\t", " ").replace("\n", " ")
        with open(HISTORY_FILE, "a") as f:
            f.write(f"{stamp}\t{flag}\t{quality}\t{int(secs)}\t{url}\t{safe_path}\n")
    except OSError:
        pass

def load_history(limit=8):
    try:
        with open(HISTORY_FILE, "r") as f:
            lines = f.read().strip().splitlines()
    except OSError:
        return []
    out = []
    for ln in lines[-limit:][::-1]:
        parts = ln.split("\t")
        # new format has 6 fields (with path); old format has 5
        if len(parts) == 6:
            out.append(tuple(parts))
        elif len(parts) == 5:
            out.append(tuple(parts) + ("",))
    return out

def find_rip():
    rip = shutil.which("rip")
    if rip:
        return rip
    cand = os.path.expanduser("~/.local/bin/rip")  # pipx location
    if os.path.exists(cand):
        return cand
    sys.exit("ERROR: streamrip 'rip' command not found. Re-run the installer.")

def read_tidal_field(field):
    try:
        with open(CONFIG, "r") as f:
            txt = f.read()
    except OSError:
        return None
    in_tidal = False
    for line in txt.splitlines():
        s = line.strip()
        if s.startswith("["):
            in_tidal = (s == "[tidal]")
            continue
        if in_tidal and s.startswith(field):
            m = re.search(r'=\s*"?([^"\n]*)"?', s)
            if m:
                return m.group(1).strip()
    return None

def token_remaining():
    val = read_tidal_field("token_expiry")
    if not val:
        return None
    try:
        return float(val) - time.time()
    except ValueError:
        return None

def has_token():
    val = read_tidal_field("access_token")
    return bool(val and val.strip())

def fmt_remaining(sec):
    if sec is None:
        return f"{RED}not logged in{RESET}"
    if sec <= 0:
        return f"{YELLOW}expired, auto-refresh on download{RESET}"
    d = int(sec // 86400)
    h = int((sec % 86400) // 3600)
    m = int((sec % 3600) // 60)
    col = YELLOW if sec < 86400 else GREEN
    return f"{col}{d}d {h:02d}h {m:02d}m{RESET}"

def fmt_dur(secs):
    secs = int(secs)
    m, s = divmod(secs, 60)
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"

def enter_raw():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    sys.stdout.write(HIDE); sys.stdout.flush()
    return old

def exit_raw(old):
    termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old)
    sys.stdout.write(SHOW); sys.stdout.flush()

def read_burst(timeout=None):
    r, _, _ = select.select([sys.stdin], [], [], timeout)
    if not r:
        return ""
    first = os.read(sys.stdin.fileno(), 4096)
    if first == b"":
        return None
    data = first
    while True:
        r, _, _ = select.select([sys.stdin], [], [], 0.02)
        if not r:
            break
        more = os.read(sys.stdin.fileno(), 4096)
        if not more:
            break
        data += more
    return data.decode("utf-8", "ignore")

def cleanup():
    sys.stdout.write(SHOW + RESET + "\n")
    sys.stdout.flush()

def quit_with_login_hint():
    cleanup()
    cmd = login_command()
    print(f"{YELLOW}No valid TIDAL login found.{RESET}")
    print(f"{GREY}Run this once to log in (your browser will open):{RESET}\n")
    print(f"  {WHITE}{cmd}{RESET}\n")
    print(f"{GREY}Then run tidaldl again.{RESET}")
    os._exit(0)

def draw(quality_idx, notice="", pasted="", countdown=None):
    sys.stdout.write(CLEAR + BG)
    rem = fmt_remaining(token_remaining())
    out = []
    out.append(f"{BG}{CYAN}{BOLD}  PASTE TIDAL LINK {RESET}{BG}{GREY} {PASTE_HINT} then it auto-starts   v{VERSION}{RESET}")
    out.append("")
    shown = pasted if pasted else f"{GREY}waiting for paste...{RESET}"
    out.append(f"  {WHITE}[ {RESET}{shown}{WHITE} ]{RESET}")
    out.append("")
    out.append(f"  {GREY}quality (up/down, space to set){RESET}")
    for i, (_qid, label) in enumerate(QUALITIES):
        if i == quality_idx:
            out.append(f"  {GREEN}{BOLD}> {label}{RESET}")
        else:
            out.append(f"  {GREY}  {label}{RESET}")
    out.append("")
    out.append(f"  {GREY}token {RESET}{rem}")
    out.append(f"  {GREY}saves to {WHITE}{DOWNLOAD_DIR}{RESET}")
    out.append("")
    hist = load_history(limit=6)
    if hist:
        out.append(f"  {GREY}recent downloads{RESET}")
        for stamp, flag, q, secs, url, path in hist:
            mark = f"{GREEN}{CHECK}{RESET}" if flag == "ok" else f"{RED}x{RESET}"
            if path:
                folder = os.path.dirname(path)
                disp = folder.replace(os.path.expanduser("~"), "~")
            else:
                disp = DOWNLOAD_DIR.replace(os.path.expanduser("~"), "~")
            out.append(f"   {mark} {GREY}{stamp}  {WHITE}{disp}{GREY}  "
                       f"q{q} {fmt_dur(secs)}{RESET}")
        out.append("")
    if countdown is not None:
        out.append(f"  {YELLOW}{BOLD}starting in {countdown}s{RESET}  "
                   f"{keycap('q', bg='203')}{GREY} cancel   "
                   f"{ESC}[48;5;46m{ESC}[38;5;232m space {RESET}{GREY} start now{RESET}")
    else:
        out.append(f"  {ESC}[48;5;51m{ESC}[38;5;232m up/dn {RESET}{GREY} quality   "
                   f"{ESC}[48;5;46m{ESC}[38;5;232m space {RESET}{GREY} set   "
                   f"{keycap('h', bg='51')}{GREY} help   "
                   f"{keycap('q', bg='203')}{GREY} quit   "
                   f"{keycap('a', bg='226', fg='232')}{GREY} authorization   "
                   f"{keycap('u', bg='46')}{GREY} update{RESET}")
    out.append("")
    if notice:
        out.append(f"  {notice}{RESET}")
    sys.stdout.write("\n".join(out))
    sys.stdout.flush()

END_MARK = "# end of tidaldl"
AUDIO_EXTS = (".flac", ".m4a", ".mp3", ".aac", ".alac", ".wav", ".ogg")

def newest_audio_file(root, since):
    """Return path of the most recently modified audio file under root that was
    written after 'since' (download start time). None if nothing new."""
    best = None
    best_mtime = since
    for dirpath, _, files in os.walk(root):
        for fn in files:
            if fn.lower().endswith(AUDIO_EXTS):
                p = os.path.join(dirpath, fn)
                try:
                    mt = os.path.getmtime(p)
                except OSError:
                    continue
                if mt >= best_mtime:
                    best_mtime = mt
                    best = p
    return best

def probe_codec(path):
    """Return (codec_name, container_ext_lower) using ffprobe, or (None, ext)."""
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None, ext
    try:
        r = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=codec_name", "-of",
             "default=nokey=1:noprint_wrappers=1", path],
            capture_output=True, text=True, timeout=15)
        codec = r.stdout.strip().lower() or None
    except (OSError, subprocess.SubprocessError):
        codec = None
    return codec, ext

def move_staged_into(stage_dir, dest_root, skip=()):
    """Move everything from the staging folder into dest_root, preserving the
    Artist - Album (Year) subfolder structure. Returns the path of the moved
    audio file (the verified FLAC), or None on failure."""
    moved_audio = None
    for dirpath, _, files in os.walk(stage_dir):
        rel = os.path.relpath(dirpath, stage_dir)
        target = dest_root if rel == "." else os.path.join(dest_root, rel)
        os.makedirs(target, exist_ok=True)
        for fn in files:
            src = os.path.join(dirpath, fn)
            if src in skip:
                continue
            dst = os.path.join(target, fn)
            try:
                shutil.move(src, dst)
            except (OSError, shutil.Error):
                try:
                    shutil.copy2(src, dst)
                except OSError:
                    continue
            if fn.lower().endswith(AUDIO_EXTS):
                moved_audio = dst
    return moved_audio

def promote_flac(stage_dir, dest_root):
    """Verify every audio file in the staging folder. Genuine FLACs (and the
    non-audio extras such as cover art) are moved into dest_root; anything else
    is left behind. Returns (last_moved_flac_or_None, flac_count, rejected)
    where rejected lists the codec/extension of every file that was refused."""
    flacs, rejected = [], []
    for dirpath, _, files in os.walk(stage_dir):
        for fn in files:
            if not fn.lower().endswith(AUDIO_EXTS):
                continue
            path = os.path.join(dirpath, fn)
            codec, ext = probe_codec(path)
            if codec is None and shutil.which("ffprobe") is None:
                codec = "flac" if ext == "flac" else None  # no ffprobe: trust extension
            if codec == "flac":
                flacs.append(path)
            else:
                rejected.append(codec or ext)
    if not flacs:
        return None, 0, rejected
    rejected_paths = set()
    for dirpath, _, files in os.walk(stage_dir):
        for fn in files:
            path = os.path.join(dirpath, fn)
            if fn.lower().endswith(AUDIO_EXTS) and path not in flacs:
                rejected_paths.add(path)
    saved = move_staged_into(stage_dir, dest_root, skip=rejected_paths)
    if not saved:
        return None, 0, rejected
    return saved, len(flacs), rejected

def clear_tidal_tokens():
    """Blank the stored TIDAL tokens in the streamrip config so the next login
    actually triggers the browser/device flow instead of reusing a stale token."""
    try:
        with open(CONFIG, "r") as f:
            txt = f.read()
    except OSError:
        return False
    lines = txt.splitlines(keepends=True)
    in_tidal = False
    fields = ("access_token", "refresh_token", "token_expiry", "user_id",
              "country_code")
    changed = False
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("["):
            in_tidal = (s == "[tidal]")
            continue
        if in_tidal:
            for fld in fields:
                if re.match(rf'^\s*{fld}\s*=', line):
                    lines[i] = re.sub(r'(=\s*).*', r'\1""', line)
                    changed = True
    if changed:
        try:
            with open(CONFIG, "w") as f:
                f.write("".join(lines))
        except OSError:
            return False
    return changed

def reauthorize():
    """Reauthorize this computer with TIDAL. Clears the stored token first so
    streamrip's login flow opens the browser, then returns to the menu. Bound to
    the A key."""
    sys.stdout.write(CLEAR + BG)
    print(f"{CYAN}{BOLD}  REAUTHORIZE TIDAL{RESET}\n")
    print(f"{GREY}  this clears the old token and logs in again so a fresh{RESET}")
    print(f"{GREY}  browser or device-code prompt appears. use it if FLAC is{RESET}")
    print(f"{GREY}  not being served or the token is missing.{RESET}\n")
    cleared = clear_tidal_tokens()
    if cleared:
        print(f"{GREY}  old token cleared.{RESET}")
    cmd = login_command()
    print(f"{GREY}  running login (watch for a URL or browser window):{RESET}\n  {WHITE}{cmd}{RESET}\n")
    try:
        subprocess.run(cmd, shell=True)
    except (OSError, subprocess.SubprocessError) as e:
        print(f"{RED}reauthorize failed: {e}{RESET}")
    print(f"\n{GREEN}{CHECK} done. press any key to go back{RESET}")
    keys = enter_raw()
    try:
        read_burst(timeout=None)
    finally:
        exit_raw(keys)

def do_download(url, quality):
    """Download safely. For FLAC requests, stage the download in a temporary
    folder first and verify the real codec there. Only a genuine FLAC is moved
    into the real download folder. If TIDAL falls back to AAC, nothing is moved,
    so an existing file is never overwritten, and the status reports that FLAC
    is not available for this track."""
    if not has_token():
        quit_with_login_hint()
    ensure_dirs()
    rip = find_rip()
    out = DOWNLOAD_DIR
    print(f"\n{GREEN}{BOLD}> downloading{RESET} {GREY}[q{quality} {QMAP[quality]}] -> {out}{RESET}")
    print(f"{GREY}{'-'*60}{RESET}\n")

    staged = (quality == 2)
    target_dir = out
    stage_dir = None
    if staged:
        stage_dir = tempfile.mkdtemp(prefix="tidaldl_stage_")
        target_dir = stage_dir

    start = time.time()
    proc = subprocess.run(
        [rip, "--quality", str(quality), "--no-db", "--folder", target_dir, "url", url]
    )
    secs = time.time() - start
    ok = (proc.returncode == 0)
    print()

    saved = None

    if ok and staged:
        saved, n_flac, rejected = promote_flac(stage_dir, out)
        if saved:
            print(f"{GREEN}{BOLD}{CHECK} done{RESET}{GREEN} in {fmt_dur(secs)}{RESET}")
            print(f"{GREY}saved file{RESET} {WHITE}{saved}{RESET}")
            print(f"{GREEN}{CHECK} verified real FLAC ({n_flac} file{'s' if n_flac != 1 else ''}){RESET}")
            if rejected:
                print(f"{YELLOW}note: {len(rejected)} track(s) came back as "
                      f"{', '.join(sorted(set(rejected)))} and were not saved{RESET}")
        elif rejected:
            # FLAC not available, TIDAL served a lower tier. Drop it.
            ok = False
            print(f"{RED}{BOLD}FLAC not available for this track.{RESET}")
            print(f"{GREY}TIDAL served {', '.join(sorted(set(rejected)))} instead. Nothing was "
                  f"downloaded and no existing file was touched.{RESET}")
        else:
            ok = False
            print(f"{YELLOW}note: nothing was produced under the staging folder{RESET}")
        shutil.rmtree(stage_dir, ignore_errors=True)
    elif ok:
        # quality 1 (AAC) requested directly, no staging needed
        saved = newest_audio_file(out, start - 2)
        print(f"{GREEN}{BOLD}{CHECK} done{RESET}{GREEN} in {fmt_dur(secs)}{RESET}")
        if saved:
            print(f"{GREY}saved file{RESET} {WHITE}{saved}{RESET}")
    else:
        print(f"{RED}x failed (exit {proc.returncode}) after {fmt_dur(secs)}{RESET}")
    if stage_dir:
        shutil.rmtree(stage_dir, ignore_errors=True)    # also when rip failed

    append_history(url, quality, secs, ok, saved or "")

    # hold the screen so streamrip's data and the verification can be read
    print(f"\n{GREY}holding {HOLD_SECS}s so you can read the result"
          f"  (press any key to continue){RESET}")
    hold_old = enter_raw()
    try:
        read_burst(timeout=HOLD_SECS)
    finally:
        exit_raw(hold_old)
    return ok

def countdown_then_download(url, quality_idx):
    quality = QUALITIES[quality_idx][0]
    remaining = COUNTDOWN_SECS
    tick = time.time()
    while remaining > 0:
        draw(quality_idx, pasted=url, countdown=remaining)
        key = read_burst(timeout=0.2)
        if key is None:
            return "cancel"
        if key:
            low = key.lower()
            if "q" in low:
                return "cancel"
            if " " in key or "\r" in key or "\n" in key:
                break
        if time.time() - tick >= 1.0:
            remaining -= 1
            tick = time.time()
    return ("go", url, quality)

def fetch_text(url, timeout=20):
    import urllib.request
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read().decode("utf-8")

def remote_version(text):
    m = re.search(r"^VERSION = (\d+)$", text, re.M)
    return int(m.group(1)) if m else None

def validate_download(text):
    """Three checks plus the fourth the manifest asks for: size plausible,
    shebang first, it compiles, and the end-of-file marker proves it is whole."""
    if len(text) < 8000:
        return "too small to be tidaldl"
    if not text.startswith("#!/usr/bin/env python3"):
        return "not a script (no shebang)"
    try:
        compile(text, "tidaldl.py", "exec")
    except SyntaxError as e:
        return f"does not parse: {e.msg}"
    if not text.rstrip().endswith(END_MARK):
        return "cut short (end marker missing)"
    if remote_version(text) is None:
        return "no VERSION found"
    return None

def run_update(raw_state):
    """U key. Shows installed -> available, asks y, replaces this file by
    writing beside it and renaming over the top. Returns a notice string."""
    sys.stdout.write(CLEAR + BG)
    print(f"{CYAN}{BOLD}  UPDATE{RESET}\n")
    try:
        text = fetch_text(UPDATE_URL)
    except Exception as e:  # network, DNS, 404: all mean "could not check"
        print(f"{RED}  could not reach {UPDATE_URL}{RESET}\n{GREY}  {e}{RESET}")
        print(f"\n{GREY}  nothing was changed. press any key to go back{RESET}")
        read_burst(timeout=None)
        return f"{YELLOW}update check failed{RESET}"
    avail = remote_version(text)
    print(f"{GREY}  installed {WHITE}v{VERSION}{GREY} -> available {WHITE}v{avail}{RESET}\n")
    if avail is None or avail <= VERSION:
        print(f"{GREEN}  already on the latest. nothing to do.{RESET}")
        print(f"\n{GREY}  press any key to go back{RESET}")
        read_burst(timeout=None)
        return f"{GREEN}v{VERSION} is current{RESET}"
    bad = validate_download(text)
    if bad:
        print(f"{RED}  the download is not usable: {bad}.{RESET}")
        print(f"{GREY}  nothing was changed. press any key to go back{RESET}")
        read_burst(timeout=None)
        return f"{RED}update refused: {bad}{RESET}"
    print(f"{YELLOW}  install v{avail}? press y to update, anything else cancels{RESET}")
    key = read_burst(timeout=None)
    if not key or key.strip().lower() != "y":
        return f"{YELLOW}update cancelled{RESET}"
    target = os.path.realpath(sys.argv[0] if os.path.basename(sys.argv[0]) != "-c" else __file__)
    tmp = target + ".new"
    try:
        # keep the installed shebang: Termux points it at its own python
        try:
            with open(target) as f:
                first = f.readline().rstrip("\n")
            if first.startswith("#!"):
                text = first + "\n" + text.split("\n", 1)[1]
        except OSError:
            pass
        with open(tmp, "w") as f:
            f.write(text)
        os.chmod(tmp, 0o755)
        os.replace(tmp, target)
    except OSError as e:
        print(f"{RED}  could not write {target}: {e}{RESET}")
        print(f"{GREY}  nothing was changed. press any key to go back{RESET}")
        try:
            os.remove(tmp)
        except OSError:
            pass
        read_burst(timeout=None)
        return f"{RED}update failed{RESET}"
    print(f"{GREEN}  {CHECK} updated to v{avail}. restarting.{RESET}")
    time.sleep(0.6)
    exit_raw(raw_state)
    cleanup()
    os.execv(sys.executable, [sys.executable, target])

def show_help():
    sys.stdout.write(CLEAR + BG)
    print(f"{CYAN}{BOLD}  PASTE TIDAL LINK then it auto-starts{RESET}\n")
    print(f"{GREY}  paste an album, track, playlist or artist link with{RESET}")
    print(f"{GREY}  {PASTE_HINT}. extra path bits like /u are stripped. a 10s{RESET}")
    print(f"{GREY}  countdown begins, then download starts. q cancels,{RESET}")
    print(f"{GREY}  space/enter starts now. streamrip shows each filename,{RESET}")
    print(f"{GREY}  bar and speed live. folders are named cleanly as{RESET}")
    print(f"{GREY}  Artist - Album (Year). saves to{RESET}")
    print(f"{GREY}  {WHITE}{DOWNLOAD_DIR}{GREY}.{RESET}\n")
    print(f"  {ESC}[48;5;51m{ESC}[38;5;232m up/dn {RESET}{GREY} move quality highlight{RESET}")
    print(f"  {ESC}[48;5;46m{ESC}[38;5;232m space {RESET}{GREY} set highlighted quality{RESET}")
    print(f"  {keycap('h', bg='51')}{GREY} this help{RESET}")
    print(f"  {keycap('q', bg='203')}{GREY} quit{RESET}")
    print(f"  {keycap('a', bg='226', fg='232')}{GREY} authorization (reauthorize this device with TIDAL){RESET}")
    print(f"  {keycap('u', bg='46')}{GREY} update (shows installed and available version, asks y){RESET}\n")
    print(f"{GREY}  FLAC safety: a FLAC download is staged and verified with{RESET}")
    print(f"{GREY}  ffprobe before it is saved. if TIDAL has no FLAC for the{RESET}")
    print(f"{GREY}  track and falls back to AAC, nothing is downloaded and no{RESET}")
    print(f"{GREY}  existing file is overwritten. you just get FLAC not available.{RESET}\n")
    print(f"{GREY}  login command if token is missing:{RESET}\n")
    print(f"  {WHITE}{login_command()}{RESET}\n")
    print(f"{GREY}  press any key to go back{RESET}")
    read_burst(timeout=None)

def set_in_section(text, section, key, value):
    """Set key = value inside [section] of a TOML text. Returns (text, found).
    Adds the key at the end of the section when it is missing."""
    lines = text.splitlines(keepends=True)
    in_sec = False
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("["):
            if in_sec:
                lines.insert(i, f"{key} = {value}\n")
                return "".join(lines), True
            in_sec = (s == f"[{section}]")
            continue
        if in_sec and re.match(rf"^\s*{re.escape(key)}\s*=", line):
            lines[i] = re.sub(r"(=\s*).*", lambda m: m.group(1) + value, line)
            return "".join(lines), True
    if in_sec:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        lines.append(f"{key} = {value}\n")
        return "".join(lines), True
    return "".join(lines), False

def patch_streamrip_config(txt, dl_dir):
    """Pure function: the streamrip config text in, the tidaldl settings out.
    Returns (new_text, report_lines)."""
    report = []
    txt, n1 = re.subn(r'(\nfolder\s*=\s*)"[^"]*"', lambda m: m.group(1) + '"%s"' % dl_dir, txt, count=1)
    report.append(f"folder -> {dl_dir}" if n1 else "folder unchanged")
    txt, n2 = re.subn(r'(\nfolder_format\s*=\s*)"[^"]*"',
                      lambda m: m.group(1) + '"{albumartist} - {title} ({year})"', txt, count=1)
    report.append("folder_format -> {albumartist} - {title} ({year})" if n2 else "folder_format unchanged")
    txt, n3 = re.subn(r'(\ntrack_format\s*=\s*)"[^"]*"',
                      lambda m: m.group(1) + '"{tracknumber:02}. {artist} - {title}"', txt, count=1)
    report.append("track_format -> {tracknumber:02}. {artist} - {title}" if n3 else "track_format unchanged")
    # pin tidal quality 2 so a stale value can never silently downgrade FLAC to AAC
    txt, n4 = set_in_section(txt, "tidal", "quality", "2")
    txt, n5 = set_in_section(txt, "tidal", "download_videos", "false")
    report.append("tidal quality pinned -> 2 (16/44.1 FLAC)" if n4 else "tidal quality unchanged")
    report.append("tidal download_videos -> false" if n5 else "download_videos unchanged")
    return txt, report

def setup_streamrip():
    """tidaldl --setup: make sure streamrip has a config, then patch it."""
    ensure_dirs()
    if not os.path.isfile(CONFIG):
        rip = shutil.which("rip") or os.path.expanduser("~/.local/bin/rip")
        try:
            # 'config path' creates the default file without opening an editor
            subprocess.run([rip, "config", "path"], capture_output=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        with open(CONFIG, "r") as f:
            txt = f.read()
    except OSError:
        print(f"streamrip config not found at {CONFIG}")
        return 1
    new, report = patch_streamrip_config(txt, DOWNLOAD_DIR)
    if new != txt:
        with open(CONFIG + ".tmp", "w") as f:
            f.write(new)
        os.replace(CONFIG + ".tmp", CONFIG)
    for line in report:
        print("   " + line)
    return 0

def main():
    ensure_dirs()
    quality = load_quality()
    quality_idx = 0 if quality == QUALITIES[0][0] else 1

    if len(sys.argv) > 1 and sys.argv[1] in ("--version", "-V"):
        print(f"tidaldl v{VERSION}")
        return
    if len(sys.argv) > 1 and sys.argv[1] == "--setup":
        sys.exit(setup_streamrip())
    if len(sys.argv) > 1:
        url = clean_tidal_url(sys.argv[1])
        if url:
            if not has_token():
                quit_with_login_hint()
            do_download(url, quality)
        else:
            print(f"{RED}Not a valid TIDAL link.{RESET}")
        return

    old = enter_raw()
    notice = ""
    pasted = ""
    try:
        while True:
            draw(quality_idx, notice=notice, pasted=pasted)
            notice = ""
            key = read_burst(timeout=None)
            if key is None:
                break
            if not key:
                continue
            if key == f"{ESC}[A":
                quality_idx = 0; quality = QUALITIES[0][0]; continue
            if key == f"{ESC}[B":
                quality_idx = 1; quality = QUALITIES[1][0]; continue
            if len(key.strip()) > 3:
                url = extract_tidal_url(key)
                if url:
                    pasted = url
                    result = countdown_then_download(url, quality_idx)
                    if result == "cancel":
                        pasted = ""; notice = f"{YELLOW}cancelled{RESET}"; continue
                    if isinstance(result, tuple) and result[0] == "go":
                        _, u, q = result
                        exit_raw(old)
                        do_download(u, q)
                        old = enter_raw()
                        pasted = ""
                        continue
                else:
                    pasted = key.strip()[:60]
                    notice = (f"{RED}not a tidal link{RESET}  "
                              f"{keycap('q', bg='203')}{GREY} clear{RESET}")
                    continue
            low = key.lower()
            if low == "q":
                if pasted:
                    pasted = ""; continue
                break
            elif low == "h":
                show_help(); continue
            elif low == "u":
                notice = run_update(old)      # stays in single-key mode: "any key" means any key
                continue
            elif low == "a":
                exit_raw(old)
                reauthorize()
                old = enter_raw()
                notice = f"{GREEN}reauthorized{RESET}"
                continue
            elif key in (" ", "\r", "\n"):
                quality = QUALITIES[quality_idx][0]
                save_quality(quality)
                notice = f"{GREEN}quality set: {QMAP[quality]}{RESET}"
                continue
    finally:
        exit_raw(old)
    cleanup()

if __name__ == "__main__":
    main()

# end of tidaldl
