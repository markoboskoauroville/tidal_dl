#!/usr/bin/env python3
"""The delivery gates (Mantra delivery-gate.md), sized for this app. Counts, not adjectives.
Exit 1 on any FAIL. SKIP means the tool was not on this machine and is named in the record."""
import ast, os, re, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
results = []

def gate(name, status, detail):
    results.append((name, status, detail))
    print(f"{name:16s} {status:5s} {detail}")

def sh(*a, **k):
    return subprocess.run(a, capture_output=True, text=True, **k)

def tool(name):
    cand = shutil.which(name) or os.path.join(os.path.dirname(sys.executable), name)
    return cand if os.path.exists(cand) else None

TRACKED = sh("git", "ls-files").stdout.split()
UNTRACKED = sh("git", "ls-files", "--others", "--exclude-standard").stdout.split()
FILES = [f for f in TRACKED + UNTRACKED if os.path.isfile(f)]

# G1 provenance
with open("tidaldl.py") as f:
    src = f.read()
version = re.search(r"^VERSION = (\d+)$", src, re.M).group(1)
fresh = sh(sys.executable, "tools/build_installers.py", "--check")
dirty = [l for l in sh("git", "status", "--porcelain").stdout.splitlines() if l.strip()]
hdrs = 0
for inst in ("install-macos.sh", "install-termux.sh"):
    with open(inst) as f:
        if f"v{version}" in f.read(400):
            hdrs += 1
prob = []
if fresh.returncode:
    prob.append("installer stale")
if hdrs != 2:
    prob.append("installer header version differs from VERSION")
with open("HANDOFF.md") as f:
    if not re.search(rf"^Version: {version}\b", f.read(), re.M):
        prob.append("HANDOFF.md does not state the version")
gate("G1 provenance", "FAIL" if prob else "pass",
     f"version {version}; 2/2 installers fresh and stamped; {len(dirty)} uncommitted path(s)"
     + ("; " + ", ".join(prob) if prob else ""))

# G2 secrets: working files and the whole history, by shape (going-public.md; AQ. first)
SHAPES = re.compile(
    r"AQ\.[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{30,}|sk-ant-[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9_-]{32,}|"
    r"sk_[A-Za-z0-9]{30,}|gsk_[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"hf_[A-Za-z0-9]{30,}|xox[bpa]-[0-9A-Za-z-]{10,}|-----BEGIN [A-Z ]*PRIVATE")
hits = 0
for f in FILES:
    try:
        with open(f, errors="ignore") as fh:
            hits += len(SHAPES.findall(fh.read()))
    except OSError:
        pass
hist = sh("git", "log", "-p", "--all").stdout
commits = len(sh("git", "rev-list", "--all").stdout.split())
hhits = len(SHAPES.findall(hist))
gate("G2 secrets", "FAIL" if hits or hhits else "pass",
     f"{len(FILES)} files, {commits} commits, {hits + hhits} hits")

# G3 analysis
bad = 0
for f in [x for x in FILES if x.endswith(".py")]:
    if sh(sys.executable, "-m", "py_compile", f).returncode:
        bad += 1
for f in ("install-macos.sh", "install-termux.sh"):
    if sh("bash", "-n", f).returncode:
        bad += 1
notes = []
pf = tool("pyflakes")
if pf:
    r = sh(pf, *[x for x in FILES if x.endswith(".py")])
    n = len(r.stdout.splitlines()); bad += n; notes.append(f"pyflakes {n}")
else:
    notes.append("pyflakes SKIPPED")
sc = tool("shellcheck")
if sc:
    r = sh(sc, "-S", "warning", "src/macos.sh.in", "src/termux.sh.in")
    n = len(re.findall(r"^In ", r.stdout, re.M)); bad += n; notes.append(f"shellcheck {n}")
else:
    notes.append("shellcheck SKIPPED")
gate("G3 analysis", "FAIL" if bad else "pass", f"{bad} problems; " + ", ".join(notes))

# G4 dead code
vu = tool("vulture")
if vu:
    r = sh(vu, "tidaldl.py", "--min-confidence", "60")
    n = len(r.stdout.splitlines())
    gate("G4 dead code", "FAIL" if n else "pass", f"{n} unused names at >=60% confidence")
else:
    gate("G4 dead code", "SKIP", "vulture not installed")

# G5 loops and waits: every while loop and every external wait is listed with its bound
tree = ast.parse(src)
whiles = [n for n in ast.walk(tree) if isinstance(n, ast.While)]
# The three loops, each examined: the countdown (ends after COUNTDOWN_SECS ticks, or a key),
# read_burst's drain (ends at the first 20 ms of silence), the menu (ends when the person quits
# or stdin closes). A fourth loop must be examined by hand and this number raised on purpose.
EXPECTED_WHILES = 3
externals = []
for n in ast.walk(tree):
    if isinstance(n, ast.Call):
        name = ast.unparse(n.func)
        if name in ("subprocess.run", "urllib.request.urlopen", "select.select"):
            has_to = any(k.arg == "timeout" for k in n.keywords) or (name == "select.select" and len(n.args) >= 4)
            externals.append((n.lineno, name, has_to))
# unbounded by design: the download itself and the login (the person watches and can Ctrl-C),
# select with timeout=None for "press any key" screens
undeadlined = [e for e in externals if not e[2]]
UNBOUNDED_OK = {"subprocess.run": 2, "select.select": 0}
unexpected = [e for e in undeadlined if e[1] == "subprocess.run"][UNBOUNDED_OK["subprocess.run"]:]
gate("G5 dead loops", "FAIL" if unexpected or len(whiles) != EXPECTED_WHILES else "pass",
     f"{len(whiles)} while loops; {len(externals)} external waits, {len(externals) - len(undeadlined)} with a deadline, "
     f"{len(undeadlined)} without (download, login: the person is watching and can Ctrl-C)")

# G8 upgrade is Test 4; run the four tests and print the counts
r = sh(sys.executable, "tests/run_all.py")
print(r.stdout.strip())
m = re.search(r"(\d+) checks, (\d+) red", r.stdout)
gate("G8 upgrade+tests", "pass" if r.returncode == 0 and m else "FAIL",
     f"{m.group(1)} checks, {m.group(2)} red (Test 4 = v21 -> v22, installers run twice over the top)" if m else r.stdout[-300:])

print("G6 stress / G7 budgets: not run (see DELIVERY_RECORD.md NOT TESTED)")
sys.exit(1 if any(s == "FAIL" for _, s, _ in results) else 0)
